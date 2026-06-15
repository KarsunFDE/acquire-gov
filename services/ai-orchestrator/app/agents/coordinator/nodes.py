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
    FinalDraftSection,
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

# Boilerplate sections (DEMO-REDESIGN-spec §2) and the FAR UCF Part they belong
# to — merged into the agent-drafted Part result at aggregate time.
BOILERPLATE_SECTION_TO_PART: dict[str, str] = {
    "D": "I", "E": "I", "F": "I", "G": "I", "K": "IV",
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
    period_of_performance: str | None
    place_of_performance: str | None
    eval_approach: str | None
    key_personnel: str | None
    user_constraints_by_section: dict[str, str]
    provenances: dict[str, str | None]
    part_iii_attachments: list[PartIIIAttachmentMeta]
    parts_to_draft: list[tuple[str, list[str]]]
    part_results: Annotated[list[PartResult], operator.add]
    boilerplate_sections: dict[str, FinalDraftSection]
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
        # DEMO-REDESIGN-spec §1 — bound the Sonnet part-drafter loop. Shared by
        # all three invoke sites below (initial + the two resume re-invokes).
        "recursion_limit": config.DRAFTER_RECURSION_LIMIT,
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


def _generate_boilerplate(state: CoordinatorState) -> dict:
    """Parallel sibling node (DEMO-REDESIGN-spec §2). Generates the boilerplate
    sections (D,E,F,G,K) the wizard hasn't already filled by hand. Single
    bounded call (D-G) + programmatic K — no agent, no loop. Merged into the
    Part I / Part IV results at aggregate time."""
    from app.agents.boilerplate import generate_boilerplate  # noqa: PLC0415

    provenances = state.get("provenances", {})
    wanted = [s for s in BOILERPLATE_SECTION_TO_PART if provenances.get(s) is None]
    if not wanted:
        return {"boilerplate_sections": {}}

    ctx = {
        "title": state.get("solicitation_id"),
        "naics": state.get("naics"),
        "set_aside": state.get("set_aside"),
        "contract_type": state.get("contract_type"),
        "period_of_performance": state.get("period_of_performance"),
        "place_of_performance": state.get("place_of_performance"),
    }
    try:
        generated = generate_boilerplate(ctx)
    except Exception as exc:  # noqa: BLE001 — boilerplate never fails the batch
        log.warning("boilerplate generation failed (%s); skipping D-G/K", exc)
        return {"boilerplate_sections": {}}

    sections = {s: generated[s] for s in wanted if s in generated}
    return {"boilerplate_sections": sections}


def _merge_boilerplate_into_parts(
    parts: dict[str, PartResult], boilerplate: dict[str, FinalDraftSection]
) -> None:
    """Fold generated D/E/F/G (Part I) and K (Part IV) into the agent-drafted
    Part results, mutating ``parts`` in place. Creates a Part result if the
    agent drafter didn't run for that Part."""
    by_part: dict[str, dict[str, FinalDraftSection]] = {}
    for sid, final in boilerplate.items():
        part = BOILERPLATE_SECTION_TO_PART.get(sid)
        if part:
            by_part.setdefault(part, {})[sid] = final
    for part, secs in by_part.items():
        existing = parts.get(part)
        if existing is not None:
            parts[part] = existing.model_copy(
                update={"sections": {**existing.sections, **secs}}
            )
        else:
            parts[part] = PartResult(
                part=part, kind="llm_drafted", sections=dict(secs)  # type: ignore[arg-type]
            )


def _aggregate(state: CoordinatorState) -> dict:
    parts: dict[str, PartResult] = {r.part: r for r in state.get("part_results", [])}
    # Fold generated boilerplate (D-G into Part I, K into Part IV) before the
    # interrupt scan and bundle assembly (DEMO-REDESIGN-spec §2).
    _merge_boilerplate_into_parts(parts, state.get("boilerplate_sections", {}))
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
    """Skipped-critic fallback (also the Phase 3 placeholder shape).

    KNOWN ISSUE (2026-06-12): Nova Lite loops on the critic harness, so the
    batch path lands here whenever the bounded critic run fails. The skip
    caveat must surface to the CO — severity warn, critic_skipped=True.
    """
    from app.api.critic import CRITIC_SKIP_REASON  # noqa: PLC0415

    return ConsistencyReport(
        solicitation_id=state["solicitation_id"],
        run_id=f"{state['solicitation_id']}:critic:{state['request_id']}",
        lm_alignment=LMAlignmentReport(
            mismatches=[], overall_severity="info",
            model="critic_skipped", input_tokens=0, output_tokens=0,
        ),
        set_aside_consistency=SetAsideConsistencyReport(
            mismatches=[], overall_severity="info"
        ),
        clin_coverage=CLINCoverageReport(gaps=[], overall_severity="info"),
        overall_severity="warn",
        blocks_submit=False,
        model_used=None,
        timestamp=datetime.now(timezone.utc),
        critic_skipped=True,
        skip_reason=CRITIC_SKIP_REASON,
    )


def _critic_sections_map(state: CoordinatorState) -> dict[str, str | None]:
    """Flatten drafted Part sections into the critic's section_id → text map."""
    out: dict[str, str | None] = {}
    for part_result in state.get("part_results", []):
        if part_result.kind != "llm_drafted":
            continue
        for sid, final in part_result.sections.items():
            text = getattr(final, "section_text", None)
            if text:
                out[sid] = text
    return out


def _run_critic(state: CoordinatorState) -> ConsistencyReport:
    """Real critic agent invocation (Phase 4 swap — was the info stub).

    Runs AFTER aggregate, batch-path mode: PartIVDrafter drafted L+M together
    so verify_l_m_consistency verifies built-in alignment (ADR-0014 D5).
    Falls back to the info stub when the critic agent errors — the batch
    bundle must never fail because the warn-only critic did.
    """
    from app.api.critic import clamp_phase1  # noqa: PLC0415

    from app.agents.critic.builder import build_consistency_critic_agent  # noqa: PLC0415

    sections = _critic_sections_map(state)
    run_id = f"{state['solicitation_id']}:critic:{state['request_id']}"
    user = (
        f"Run context: solicitation_id={state['solicitation_id']} run_id={run_id} "
        f"timestamp={datetime.now(timezone.utc).isoformat()}\n"
        f"set_aside: {state.get('set_aside') or '(none)'}\n\n"
        + ("\n\n".join(
            f"=== SECTION {sid} ===\n{text}" for sid, text in sorted(sections.items())
        ) or "(no drafted sections)")
    )
    try:
        agent = build_consistency_critic_agent()
        result = agent.invoke(
            {"messages": [{"role": "user", "content": user}]},
            config={
                "recursion_limit": config.CRITIC_RECURSION_LIMIT,
                "tags": ["m1", "consistency-critic", "batch-driven"],
                "metadata": {
                    "request_id": state["request_id"],
                    "solicitation_id": state["solicitation_id"],
                    "batch_run_id": state["batch_run_id"],
                },
            },
        )
        report: ConsistencyReport = result["structured_response"]
        report = clamp_phase1(report.model_copy(update={
            "run_id": run_id, "solicitation_id": state["solicitation_id"],
            "model_used": config.BEDROCK_CRITIC_MODEL,
        }))
        _audit_safe(
            action="consistency_critic",
            tenant_id=state["tenant_id"],
            request_id=state["request_id"],
            outcome=report.overall_severity,
            run_id=run_id,
            batch_run_id=state["batch_run_id"],
            overall_severity=report.overall_severity,
            blocks_submit=False,
        )
        return report
    except Exception as exc:  # noqa: BLE001 — warn-only critic never fails the batch
        log.warning("batch critic failed (%s); falling back to info stub", exc)
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
