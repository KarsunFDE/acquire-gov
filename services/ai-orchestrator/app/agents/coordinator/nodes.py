"""Coordinator graph nodes (ADR-0014; design ref §18.12.2).

Node inventory: ``_plan`` → ``_fan_out_per_part`` (Send) → ``_draft_part_i`` /
``_draft_part_iv`` + ``_resolve_part_ii`` + ``_pass_through_part_iii`` (all
parallel) → ``_aggregate`` → ``_route_after_aggregate`` → ``_critic`` → END.

Interrupt protocol: a Part drafter's HITL middleware pauses the CHILD agent;
the node then calls langgraph ``interrupt()`` so the PARENT coordinator pauses
too (its checkpointer persists the partial state). ``/batch/resume`` resumes
the parent with per-interrupt decision payloads which this node forwards to
the child via ``Command(resume=...)``. The pre-interrupt section of the node
is replay-safe: on resume-replay it detects the already-paused child and skips
straight to the interrupt call.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Literal, TypedDict

import operator

from app import config
from app.agents.schemas import (
    ConsistencyReport,
    CLINCoverageReport,
    LMAlignmentReport,
    PartDraftBundle,
    PartIIIAttachmentMeta,
    PartResult,
    PendingToolCall,
    SetAsideConsistencyReport,
    SolicitationDraftBundle,
)
from app.agents.coordinator.part_ii import resolve_part_ii_clauses
from app.agents.coordinator.part_iii import pass_through_part_iii

log = logging.getLogger("ai-orchestrator.coordinator")

AI_PART_TO_SECTIONS: dict[str, frozenset[str]] = {
    "I": frozenset({"C", "H"}),
    "IV": frozenset({"L", "M"}),
}


class CoordinatorState(TypedDict, total=False):
    solicitation_id: str
    tenant_id: str
    request_id: str
    batch_run_id: str
    naics: str | None
    set_aside: str | None
    contract_type: str | None
    agency_supplement: str | None
    user_constraints_by_section: dict[str, str]
    provenances: dict[str, str | None]
    part_iii_attachments: list[PartIIIAttachmentMeta]
    parts_to_draft: list[tuple[str, list[str]]]
    part_results: Annotated[list[PartResult], operator.add]
    bundle: SolicitationDraftBundle | None
    skip_critic: bool


def _plan(state: CoordinatorState) -> dict:
    parts_to_draft: list[tuple[str, list[str]]] = []
    for part, sections in AI_PART_TO_SECTIONS.items():
        still_null = sorted(
            s for s in sections if state["provenances"].get(s) is None
        )
        if still_null:
            parts_to_draft.append((part, still_null))
    if len(parts_to_draft) > config.MAX_BATCH_FAN_OUT:
        # ADR-0014 D9 hard cap — unreachable in Phase 1 (2 AI Parts == default
        # cap) but lights up if Phase 1.5 adds AI Parts without bumping it.
        raise ValueError(
            f"batch_fan_out_exceeded: {len(parts_to_draft)} > {config.MAX_BATCH_FAN_OUT}"
        )
    return {"parts_to_draft": parts_to_draft}


def _fan_out_per_part(state: CoordinatorState) -> list:
    from langgraph.types import Send  # noqa: PLC0415

    return [
        Send(f"draft_part_{part}", {
            "part": part,
            "sections": sections,
            "solicitation_id": state["solicitation_id"],
            "tenant_id": state["tenant_id"],
            "request_id": state["request_id"],
            "batch_run_id": state["batch_run_id"],
            "naics": state.get("naics"),
            "set_aside": state.get("set_aside"),
            "user_constraints_by_section": {
                s: state.get("user_constraints_by_section", {}).get(s)
                for s in sections
            },
        })
        for part, sections in state.get("parts_to_draft", [])
    ] or ["aggregate"]  # nothing to draft → straight to aggregate


def _part_user_message(payload: dict) -> str:
    constraints = "\n".join(
        f"- Section {s}: {c or '(none)'}"
        for s, c in payload["user_constraints_by_section"].items()
    )
    return (
        f"Draft FAR UCF Part {payload['part']} sections "
        f"{', '.join(payload['sections'])} for solicitation "
        f"{payload['solicitation_id']}.\n"
        f"naics: {payload.get('naics') or '(unset)'}\n"
        f"set_aside: {payload.get('set_aside') or '(unset)'}\n"
        f"user constraints by section:\n{constraints}"
    )


def _child_run_id(payload: dict) -> str:
    return f"{payload['solicitation_id']}:part_{payload['part']}:{payload['request_id']}"


def _build_part_agent(part: str):
    """Seam — tests monkeypatch this."""
    from app.agents.part_drafter.builder import build_part_drafter_agent  # noqa: PLC0415

    return build_part_drafter_agent(part)  # type: ignore[arg-type]


def _audit_safe(**kwargs: object) -> None:
    from app import audit as audit_mod  # noqa: PLC0415

    try:
        audit_mod.write_audit_log(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover
        log.error("audit write failed: %s", exc)


def _draft_part(payload: dict) -> dict:
    """Shared body for the two Part-drafter nodes (Send targets)."""
    from langgraph.types import Command, interrupt  # noqa: PLC0415

    part = payload["part"]
    agent = _build_part_agent(part)
    child_run_id = _child_run_id(payload)
    child_cfg = {
        "configurable": {"thread_id": child_run_id, "tenant_id": payload["tenant_id"]},
        "tags": ["m1", "batch", f"part-{part}"],
        "metadata": {
            "request_id": payload["request_id"],
            "solicitation_id": payload["solicitation_id"],
            "tenant_id": payload["tenant_id"],
            "batch_run_id": payload["batch_run_id"],
            "part": part,
        },
    }

    # Replay-safety: when the parent resumes, this function re-executes from
    # the top. A child already paused on its HITL gate must NOT be re-invoked
    # with fresh input — skip straight to the interrupt-resume handshake.
    snapshot = agent.get_state(child_cfg)
    child_paused = bool(snapshot.next) if snapshot else False

    result = None
    if not child_paused:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": _part_user_message(payload)}]},
            config=child_cfg,
        )

    if result is None or result.get("__interrupt__"):
        pending = _pending_from_child(result, payload, child_run_id)
        # Parent pauses HERE; resume value is the child's HITLResponse payload.
        decisions = interrupt(pending.model_dump())
        result = agent.invoke(Command(resume=decisions), config=child_cfg)
        if result.get("__interrupt__"):
            # Edit decision produced another hitl band — surface a fresh pause.
            pending = _pending_from_child(result, payload, child_run_id)
            decisions = interrupt(pending.model_dump())
            result = agent.invoke(Command(resume=decisions), config=child_cfg)

    bundle: PartDraftBundle = result["structured_response"]
    bundle = bundle.model_copy(update={
        "request_id": payload["request_id"],
        "run_id": child_run_id,
    })

    sections_by_outcome: dict[str, list[str]] = {}
    for sid, final in bundle.sections.items():
        sections_by_outcome.setdefault(final.outcome, []).append(sid)
    _audit_safe(
        action="part_drafter_run",
        tenant_id=payload["tenant_id"],
        request_id=payload["request_id"],
        outcome=bundle.overall_outcome,
        run_id=child_run_id,
        batch_run_id=payload["batch_run_id"],
        part_drafter={
            "part": part,
            "sections_requested": payload["sections"],
            "sections_drafted": sorted(sections_by_outcome.get("draft_returned", [])),
            "sections_interrupted": sorted(sections_by_outcome.get("interrupted", [])),
            "sections_withheld": sorted(sections_by_outcome.get("withheld", [])),
        },
    )

    return {
        "part_results": [
            PartResult(part=part, kind="llm_drafted", sections=dict(bundle.sections))
        ]
    }


def _pending_from_child(result: dict | None, payload: dict, child_run_id: str) -> PendingToolCall:
    """Shape the child's HITL interrupt into the Part-level pending payload."""
    args: dict = {}
    reason = "rerank_top_score in hitl band — CO review required"
    if result:
        value = getattr(result["__interrupt__"][0], "value", None)
        if isinstance(value, dict):
            requests = value.get("action_requests") or []
            if requests:
                args = requests[0].get("args") or {}
                reason = requests[0].get("description") or reason
    return PendingToolCall(
        tool_name="compute_gate_decision",
        args={**args, "part": payload["part"], "sections": payload["sections"],
              "child_run_id": child_run_id},
        reason=reason,
    )


def _draft_part_i(payload: dict) -> dict:
    return _draft_part(payload)


def _draft_part_iv(payload: dict) -> dict:
    return _draft_part(payload)


def _resolve_part_ii(state: CoordinatorState) -> dict:
    clause_list = resolve_part_ii_clauses(
        set_aside=state.get("set_aside"),
        contract_type=state.get("contract_type"),
        agency_supplement=state.get("agency_supplement"),
    )
    return {
        "part_results": [
            PartResult(part="II", kind="programmatic_resolved",
                       sections={"I": clause_list})
        ]
    }


def _pass_through_part_iii(state: CoordinatorState) -> dict:
    return {
        "part_results": [
            pass_through_part_iii(state.get("part_iii_attachments", []))
        ]
    }


def _aggregate(state: CoordinatorState) -> dict:
    parts: dict[str, PartResult] = {r.part: r for r in state.get("part_results", [])}
    interrupted = [
        final.pending_tool_call
        for r in parts.values()
        for final in r.sections.values()
        if hasattr(final, "outcome") and final.outcome == "interrupted"
        and final.pending_tool_call
    ]
    bundle = SolicitationDraftBundle(
        solicitation_id=state["solicitation_id"],
        parts=parts,  # type: ignore[arg-type]
        overall_outcome="batch_interrupted" if interrupted else "batch_completed",
        consistency_report=None,
        pending_interrupts=interrupted,
        request_id=state["request_id"],
        batch_run_id=state["batch_run_id"],
    )
    return {"bundle": bundle, "skip_critic": bool(interrupted)}


def _route_after_aggregate(state: CoordinatorState) -> str:
    from langgraph.graph import END  # noqa: PLC0415

    return END if state.get("skip_critic") else "critic"


def _stub_consistency_report(state: CoordinatorState) -> ConsistencyReport:
    """Phase 3 placeholder — Phase 4 swaps in the real critic agent."""
    return ConsistencyReport(
        solicitation_id=state["solicitation_id"],
        run_id=f"{state['solicitation_id']}:critic:{state['request_id']}",
        lm_alignment=LMAlignmentReport(
            mismatches=[], overall_severity="info",
            model="critic_stub", input_tokens=0, output_tokens=0,
        ),
        set_aside_consistency=SetAsideConsistencyReport(
            mismatches=[], overall_severity="info"
        ),
        clin_coverage=CLINCoverageReport(gaps=[], overall_severity="info"),
        overall_severity="info",
        blocks_submit=False,
        model_used=None,
        timestamp=datetime.now(timezone.utc),
    )


def _run_critic(state: CoordinatorState) -> ConsistencyReport:
    """Seam — Phase 4 replaces the stub with the real critic agent."""
    return _stub_consistency_report(state)


def _critic(state: CoordinatorState) -> dict:
    """Construct a NEW bundle with the report — never mutate state['bundle']
    in place (LangGraph state mutation is fragile under retry/replay)."""
    report = _run_critic(state)
    prior = state["bundle"]
    assert prior is not None
    return {
        "bundle": SolicitationDraftBundle(
            solicitation_id=prior.solicitation_id,
            parts=prior.parts,
            overall_outcome=prior.overall_outcome,
            consistency_report=report,
            pending_interrupts=prior.pending_interrupts,
            request_id=prior.request_id,
            batch_run_id=prior.batch_run_id,
        )
    }
