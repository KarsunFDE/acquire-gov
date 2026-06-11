"""HITL gate middleware (ADR-0012 D6; design ref §9.1).

Phase 1 status: **structurally present, interrupts disabled.** The predicate
logic below is final (Phase 2 spec) but ``HITL_INTERRUPTS_ENABLED`` is False
until Phase 2 lights it up — every Phase 1 gate decision returns ``pass``
against the seeded corpus, so no interrupt would fire anyway; the flag makes
that an invariant rather than a corpus accident.

The predicate inspects ``compute_gate_decision``'s INPUT args (the tool's
input fully determines its return — that's why gate computation is a separate
tool from retrieval) and reads the same :func:`gate_thresholds` helper as the
tool body so the two thresholds stay locked together.
"""
from __future__ import annotations

import logging

from app.agents.tools.gate import gate_thresholds

log = logging.getLogger("ai-orchestrator.middleware.hitl_gate")

# Phase 2 flips this to True (PR P2.1). Keep module-level so tests can patch.
HITL_INTERRUPTS_ENABLED = False


def _score_in_hitl_band(rerank_top_score: float | None) -> bool:
    """Pure predicate core — True when score ∈ [withhold_t, pass_t)."""
    if rerank_top_score is None:  # rerank_unavailable_passthrough — no interrupt
        return False
    withhold_t, pass_t = gate_thresholds()
    return withhold_t <= rerank_top_score < pass_t


def _interrupt_on_hitl_band(tool_call) -> bool:
    """Middleware predicate: inspect compute_gate_decision's INPUT args.

    Accepts either a dict-shaped tool call ({"name", "args"}) or an object
    with .name/.args — langchain versions differ.
    """
    if not HITL_INTERRUPTS_ENABLED:
        return False
    name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
    if name != "compute_gate_decision":
        return False
    args = tool_call.get("args") if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
    return _score_in_hitl_band((args or {}).get("rerank_top_score"))


def build_hitl_middleware():
    """Construct the HumanInTheLoopMiddleware (or None while disabled).

    Returns None in Phase 1 so ``create_agent`` receives an empty middleware
    list — structurally wired (builder filters None) without an interrupt
    surface. Phase 2 returns the real middleware.
    """
    if not HITL_INTERRUPTS_ENABLED:
        return None
    from langchain.agents.middleware import HumanInTheLoopMiddleware  # noqa: PLC0415

    return HumanInTheLoopMiddleware(
        interrupt_on={"compute_gate_decision": _interrupt_on_hitl_band}
    )
