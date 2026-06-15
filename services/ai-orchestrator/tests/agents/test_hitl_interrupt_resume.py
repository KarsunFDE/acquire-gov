"""P2.1/P2.2 — HITL middleware fire-rule + graph-level pause/resume.

Builds the REAL create_agent graph with a scripted fake chat model and an
in-memory checkpointer. The script makes the model call
``compute_gate_decision`` with a hitl-band score; the middleware must
interrupt BEFORE the tool executes; resume decisions drive the three
terminal outcomes (approve → draft, reject → withheld).

Mongo-backed restart survival is covered in tests/api/test_pause_restart.py.
"""
from __future__ import annotations

import pytest

pytest.importorskip("langchain.agents", reason="langchain v1 required")

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agents import builder as builder_mod
from app.agents.middleware import hitl_gate
from app.agents.builder import build_section_drafter_agent

# ---------------------------------------------------------------------------
# Predicate unit tests (P2.1 fire-rule — three bands + passthrough)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "should_interrupt"),
    [
        (0.0, False),    # withhold band — tool returns withhold; no interrupt
        (0.39, False),
        (0.40, True),    # hitl band lower edge
        (0.45, True),
        (0.54, True),
        (0.55, False),   # pass band
        (0.85, False),
        (None, False),   # rerank_unavailable_passthrough
    ],
)
def test_fire_rule_bands(score, should_interrupt):
    call = {"name": "compute_gate_decision", "args": {"rerank_top_score": score}}
    assert hitl_gate._interrupt_on_hitl_band(call) is should_interrupt


def test_fire_rule_ignores_other_tools():
    call = {"name": "retrieve_far_clauses", "args": {"rerank_top_score": 0.45}}
    assert hitl_gate._interrupt_on_hitl_band(call) is False


def test_fire_rule_disabled_flag(monkeypatch):
    monkeypatch.setattr(hitl_gate, "HITL_INTERRUPTS_ENABLED", False)
    call = {"name": "compute_gate_decision", "args": {"rerank_top_score": 0.45}}
    assert hitl_gate._interrupt_on_hitl_band(call) is False


def test_build_hitl_middleware_returns_middleware():
    mw = hitl_gate.build_hitl_middleware()
    assert mw is not None
    assert type(mw).__name__ == "HumanInTheLoopMiddleware"


# ---------------------------------------------------------------------------
# Graph-level interrupt + resume (scripted fake model, in-memory checkpoints)
# ---------------------------------------------------------------------------

_FINAL_ARGS = {
    "outcome": "draft_returned",
    "section_text": "L.1 GENERAL INSTRUCTIONS ...",
    "section_id": "L",
    "citations": [],
    "gate_decision": "hitl",
    "requires_human_review": True,
    "rerank_top_score": 0.45,
    "request_id": "req-1",
    "run_id": "sol-1:L:req-1",
}

_WITHHELD_ARGS = {
    **_FINAL_ARGS,
    "outcome": "withheld",
    "section_text": None,
}


def _gate_call_message(score: float = 0.45) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{
            "name": "compute_gate_decision",
            "args": {"rerank_top_score": score},
            "id": "tc-gate-1",
        }],
    )


def _structured_response_message(args: dict, name: str = "FinalDraftSection") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": "tc-final-1"}],
    )


class _ScriptedChatModel(GenericFakeChatModel):
    """GenericFakeChatModel + no-op bind_tools (scripted messages carry the
    tool calls; the agent's tool binding is irrelevant to the script)."""

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001, D102
        return self


def _agent_with_script(monkeypatch, messages):
    fake = _ScriptedChatModel(messages=iter(messages))
    monkeypatch.setattr(builder_mod, "_harness_chat", lambda: fake)
    monkeypatch.setattr(builder_mod, "build_mongodb_saver", lambda: InMemorySaver())
    return build_section_drafter_agent()


def _cfg(thread_id: str = "sol-1:L:req-1") -> dict:
    return {"configurable": {"thread_id": thread_id, "tenant_id": "tenant_A"},
            "metadata": {"tenant_id": "tenant_A"}}


def test_hitl_band_interrupts_before_tool_runs(monkeypatch):
    agent = _agent_with_script(monkeypatch, [
        _gate_call_message(0.45),
        _structured_response_message(_FINAL_ARGS),
    ])
    result = agent.invoke({"messages": [{"role": "user", "content": "draft L"}]},
                          config=_cfg())
    interrupts = result.get("__interrupt__")
    assert interrupts, "expected the middleware to pause the run"
    value = interrupts[0].value
    reqs = value["action_requests"] if isinstance(value, dict) else value[0]["action_requests"]
    assert reqs[0]["name"] == "compute_gate_decision"
    assert reqs[0]["args"]["rerank_top_score"] == 0.45
    # The gate tool must NOT have produced a ToolMessage yet.
    tool_msgs = [m for m in result["messages"] if m.type == "tool"]
    assert tool_msgs == []


def test_resume_approve_completes_draft(monkeypatch):
    agent = _agent_with_script(monkeypatch, [
        _gate_call_message(0.45),
        _structured_response_message(_FINAL_ARGS),
    ])
    cfg = _cfg("sol-1:L:req-approve")
    first = agent.invoke({"messages": [{"role": "user", "content": "draft L"}]}, config=cfg)
    assert first.get("__interrupt__")

    resumed = agent.invoke(
        Command(resume={"decisions": [{"type": "approve"}]}), config=cfg
    )
    final = resumed["structured_response"]
    assert final.outcome == "draft_returned"
    assert final.section_text.startswith("L.1")
    # The gate tool DID run after approval.
    tool_msgs = [m for m in resumed["messages"] if m.type == "tool"]
    assert any("hitl" in str(m.content) for m in tool_msgs)


def test_resume_reject_yields_withheld(monkeypatch):
    agent = _agent_with_script(monkeypatch, [
        _gate_call_message(0.45),
        _structured_response_message(_WITHHELD_ARGS),
    ])
    cfg = _cfg("sol-1:L:req-reject")
    first = agent.invoke({"messages": [{"role": "user", "content": "draft L"}]}, config=cfg)
    assert first.get("__interrupt__")

    resumed = agent.invoke(
        Command(resume={"decisions": [{"type": "reject", "message": "lean corpus — type by hand"}]}),
        config=cfg,
    )
    final = resumed["structured_response"]
    assert final.outcome == "withheld"
    assert final.section_text is None


def test_resume_edit_reruns_gate_with_edited_args(monkeypatch):
    agent = _agent_with_script(monkeypatch, [
        _gate_call_message(0.45),
        _structured_response_message(_FINAL_ARGS),
    ])
    cfg = _cfg("sol-1:L:req-edit")
    first = agent.invoke({"messages": [{"role": "user", "content": "draft L"}]}, config=cfg)
    assert first.get("__interrupt__")

    resumed = agent.invoke(
        Command(resume={"decisions": [{
            "type": "edit",
            "edited_action": {"name": "compute_gate_decision",
                              "args": {"rerank_top_score": 0.80}},
        }]}),
        config=cfg,
    )
    # Edited score 0.80 → pass band; gate tool ran with the edited args.
    tool_msgs = [m for m in resumed["messages"] if m.type == "tool"]
    assert any('"pass"' in str(m.content) or "pass" in str(m.content) for m in tool_msgs)
    assert resumed["structured_response"].outcome == "draft_returned"


def test_pass_band_does_not_interrupt(monkeypatch):
    agent = _agent_with_script(monkeypatch, [
        _gate_call_message(0.85),
        _structured_response_message({**_FINAL_ARGS, "gate_decision": "pass",
                                      "requires_human_review": False,
                                      "rerank_top_score": 0.85}),
    ])
    result = agent.invoke({"messages": [{"role": "user", "content": "draft L"}]},
                          config=_cfg("sol-1:L:req-pass"))
    assert not result.get("__interrupt__")
    assert result["structured_response"].outcome == "draft_returned"
