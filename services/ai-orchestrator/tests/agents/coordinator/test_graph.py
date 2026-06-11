"""P3.5 — coordinator graph integration tests (ADR-0014).

Runs the REAL compiled StateGraph with fake Part-drafter children and an
in-memory checkpointer. Covers: full fan-out, provenance skipping, Part-level
interrupt propagation to a paused parent, and resume-to-completion.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("langgraph.graph", reason="langgraph required")

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app import audit as audit_mod
from app.agents.coordinator import graph as graph_mod
from app.agents.coordinator import nodes as nodes_mod
from app.agents.schemas import FinalDraftSection, PartDraftBundle


def _final(section_id: str, outcome: str = "draft_returned") -> FinalDraftSection:
    return FinalDraftSection(
        outcome=outcome,  # type: ignore[arg-type]
        section_text=f"{section_id} text" if outcome == "draft_returned" else None,
        section_id=section_id,  # type: ignore[arg-type]
        citations=[],
        gate_decision="pass" if outcome == "draft_returned" else "hitl",
        requires_human_review=outcome != "draft_returned",
        rerank_top_score=0.8,
        request_id="req-b",
        run_id=f"sol-b:{section_id}:req-b",
    )


def _bundle(part: str, sections: list[str]) -> PartDraftBundle:
    return PartDraftBundle(
        part=part,  # type: ignore[arg-type]
        sections={s: _final(s) for s in sections},
        overall_outcome="draft_returned",
        pending_tool_call=None,
        rerank_top_score=0.8,
        request_id="req-b",
        run_id=f"sol-b:part_{part}:req-b",
    )


class _FakeChild:
    """Stands in for a PartDrafterAgent. Optionally interrupts once."""

    def __init__(self, part: str, sections: list[str], interrupt_first: bool = False):
        self.part = part
        self.sections = sections
        self.interrupt_first = interrupt_first
        self.paused = False
        self.invocations: list[Any] = []

    def get_state(self, cfg):
        return SimpleNamespace(next=("tools",) if self.paused else ())

    def invoke(self, payload, config=None):
        self.invocations.append(payload)
        if isinstance(payload, Command):
            # resume → complete
            self.paused = False
            return {"structured_response": _bundle(self.part, self.sections)}
        if self.interrupt_first and not self.paused:
            self.paused = True
            return {"__interrupt__": [SimpleNamespace(value={
                "action_requests": [{
                    "name": "compute_gate_decision",
                    "args": {"rerank_top_score": 0.45},
                    "description": "hitl band — CO review required",
                }],
                "review_configs": [],
            })]}
        return {"structured_response": _bundle(self.part, self.sections)}


@pytest.fixture()
def env(monkeypatch):
    children: dict[str, _FakeChild] = {
        "I": _FakeChild("I", ["C", "H"]),
        "IV": _FakeChild("IV", ["L", "M"]),
    }
    monkeypatch.setattr(nodes_mod, "_build_part_agent", lambda part: children[part])
    monkeypatch.setattr(audit_mod, "write_audit_log", lambda *a, **k: "id")
    monkeypatch.setattr(graph_mod, "build_mongodb_saver", lambda: InMemorySaver())
    graph_mod.build_coordinator_graph.cache_clear()
    yield children
    graph_mod.build_coordinator_graph.cache_clear()


def _state(provenances: dict | None = None) -> dict:
    return {
        "solicitation_id": "sol-b",
        "tenant_id": "tenant_A",
        "request_id": "req-b",
        "batch_run_id": "sol-b:batch:req-b",
        "naics": "541512",
        "set_aside": "SDVOSB",
        "contract_type": "FFP",
        "agency_supplement": "GSAM",
        "user_constraints_by_section": {"C": "quarterly"},
        "provenances": provenances or {"C": None, "H": None, "L": None, "M": None},
        "part_iii_attachments": [],
        "part_results": [],
        "bundle": None,
        "skip_critic": False,
    }


def _cfg(thread: str) -> dict:
    return {"configurable": {"thread_id": thread, "tenant_id": "tenant_A"},
            "metadata": {"tenant_id": "tenant_A"}}


def test_full_batch_completes_with_four_parts(env):
    graph = graph_mod.build_coordinator_graph()
    result = graph.invoke(_state(), config=_cfg("t-full"))
    bundle = result["bundle"]
    assert bundle.overall_outcome == "batch_completed"
    assert set(bundle.parts) == {"I", "II", "III", "IV"}
    assert bundle.parts["I"].kind == "llm_drafted"
    assert bundle.parts["II"].kind == "programmatic_resolved"
    assert bundle.parts["III"].kind == "wizard_provided"
    assert bundle.parts["IV"].kind == "llm_drafted"
    # Part II carries the deterministic Section I clause list.
    clause_list = bundle.parts["II"].sections["I"]
    assert any(c.citation == "52.219-27" for c in clause_list.clauses_by_reference)
    # Critic stub ran (no interrupts) — info severity, never blocks submit.
    assert bundle.consistency_report is not None
    assert bundle.consistency_report.overall_severity == "info"
    assert bundle.consistency_report.blocks_submit is False


def test_pre_owned_sections_skip_their_part(env):
    graph = graph_mod.build_coordinator_graph()
    result = graph.invoke(
        _state({"C": "human", "H": "ai-edited", "L": None, "M": None}),
        config=_cfg("t-skip"),
    )
    bundle = result["bundle"]
    assert "I" not in bundle.parts          # Part I fully owned → never drafted
    assert env["I"].invocations == []       # zero spend on the owned Part
    assert bundle.parts["IV"].kind == "llm_drafted"
    assert bundle.overall_outcome == "batch_completed"


def test_part_interrupt_pauses_parent_and_preserves_sibling(env):
    env["IV"].interrupt_first = True
    graph = graph_mod.build_coordinator_graph()
    result = graph.invoke(_state(), config=_cfg("t-intr"))

    interrupts = result.get("__interrupt__")
    assert interrupts, "parent coordinator must pause on a Part interrupt"
    value = interrupts[0].value
    assert value["tool_name"] == "compute_gate_decision"
    assert value["args"]["part"] == "IV"
    assert value["args"]["sections"] == ["L", "M"]
    # Sibling Part I completed and its result is preserved in state.
    parts = {r.part for r in result.get("part_results", [])}
    assert "I" in parts
    # No bundle yet — aggregate hasn't run.
    assert result.get("bundle") is None


def test_resume_completes_interrupted_batch(env):
    env["IV"].interrupt_first = True
    graph = graph_mod.build_coordinator_graph()
    cfg = _cfg("t-resume")
    first = graph.invoke(_state(), config=cfg)
    assert first.get("__interrupt__")

    resumed = graph.invoke(
        Command(resume={"decisions": [{"type": "approve"}]}), config=cfg
    )
    bundle = resumed["bundle"]
    assert bundle.overall_outcome == "batch_completed"
    assert set(bundle.parts) == {"I", "II", "III", "IV"}
    # Sibling Part I was NOT re-drafted on resume (one original invocation).
    non_command = [p for p in env["I"].invocations if not isinstance(p, Command)]
    assert len(non_command) == 1
    # Part IV resumed via Command exactly once.
    commands = [p for p in env["IV"].invocations if isinstance(p, Command)]
    assert len(commands) == 1
    assert bundle.consistency_report is not None
