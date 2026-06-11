"""HITL gate middleware (ADR-0012 D6; design ref §9.1) — LIVE since Phase 2.

The predicate inspects ``compute_gate_decision``'s INPUT args (the tool's
input fully determines its return — that's why gate computation is a separate
tool from retrieval) and reads the same :func:`gate_thresholds` helper as the
tool body so the two thresholds stay locked together.

Interrupting on the gate tool (not ``draft_section_text``) means the CO
pre-approves BEFORE the Sonnet spend, not after (design ref §9.1 rationale).
"""
from __future__ import annotations

import logging

from app.agents.tools.gate import gate_thresholds

log = logging.getLogger("ai-orchestrator.middleware.hitl_gate")

# Phase 2 (P2.1) lit this up. Kept as a module flag so tests can isolate the
# Phase 1 no-interrupt behavior and ops can emergency-disable via monkeypatch.
HITL_INTERRUPTS_ENABLED = True


def _score_in_hitl_band(rerank_top_score: float | None) -> bool:
    """Pure predicate core — True when score ∈ [withhold_t, pass_t)."""
    if rerank_top_score is None:  # rerank_unavailable_passthrough — no interrupt
        return False
    withhold_t, pass_t = gate_thresholds()
    return withhold_t <= rerank_top_score < pass_t


def _interrupt_on_hitl_band(request) -> bool:
    """``when`` predicate for InterruptOnConfig — receives a ToolCallRequest.

    Tolerates three shapes (langchain versions / unit tests differ):
    ToolCallRequest (``.tool_call`` dict), a bare tool-call dict
    ({"name", "args"}), or an object with .name/.args.
    """
    if not HITL_INTERRUPTS_ENABLED:
        return False
    tool_call = getattr(request, "tool_call", None)
    if tool_call is None:
        tool_call = request
    if isinstance(tool_call, dict):
        name = tool_call.get("name")
        args = tool_call.get("args") or {}
    else:
        name = getattr(tool_call, "name", None)
        args = getattr(tool_call, "args", None) or {}
    if name != "compute_gate_decision":
        return False
    return _score_in_hitl_band(args.get("rerank_top_score"))


def hitl_reason(rerank_top_score: float | None) -> str:
    """Human-facing interrupt reason string (design ref §4.1 PendingToolCall)."""
    withhold_t, pass_t = gate_thresholds()
    return (
        f"rerank_top_score {rerank_top_score} in [{withhold_t:.2f}, {pass_t:.2f}) "
        f"— CO review required"
    )


def _describe(tool_call, state, runtime) -> str:  # noqa: ANN001 — langchain protocol
    return hitl_reason((tool_call.get("args") or {}).get("rerank_top_score"))


def build_hitl_middleware():
    """Construct the HumanInTheLoopMiddleware (or None when disabled)."""
    if not HITL_INTERRUPTS_ENABLED:
        return None
    from langchain.agents.middleware import HumanInTheLoopMiddleware  # noqa: PLC0415
    from langchain.agents.middleware.human_in_the_loop import (  # noqa: PLC0415
        InterruptOnConfig,
    )

    return HumanInTheLoopMiddleware(
        interrupt_on={
            "compute_gate_decision": InterruptOnConfig(
                allowed_decisions=["approve", "edit", "reject"],
                when=_interrupt_on_hitl_band,
                description=_describe,
            )
        },
        description_prefix="Gate decision requires CO review",
    )
