"""``compute_gate_decision`` — programmatic gate tool (design ref §8.4).

The agent passes the rerank top-score it observed from retrieve_far_clauses.
The HITL middleware predicate (Phase 2) inspects this tool's INPUT args and
interrupts when the score lands in [withhold_threshold, pass_threshold).
Tool body and middleware read the same :func:`gate_thresholds` helper so the
two stay locked together (ADR-0012 D6).
"""
from __future__ import annotations

from langchain.tools import tool

from app import config
from app.agents.schemas import GateDecisionResult


def gate_thresholds() -> tuple[float, float]:
    """Returns (withhold_threshold, pass_threshold). Single source for D6."""
    return config.GATE_WITHHOLD_THRESHOLD, config.GATE_PASS_THRESHOLD


@tool
def compute_gate_decision(rerank_top_score: float | None) -> GateDecisionResult:
    """Decide pass / hitl / withhold from a rerank top-score per ADR-0007 D3.

    Call this after retrieval and BEFORE drafting. Pass the rerank_top_score
    you observed from retrieve_far_clauses (null if rerank was degraded).
    If the result is "withhold", terminate without drafting.
    """
    withhold_t, pass_t = gate_thresholds()
    if rerank_top_score is None:
        return GateDecisionResult(
            gate_decision="rerank_unavailable_passthrough",
            rerank_top_score=None,
            reason="rerank outage — proceeding with degraded mode + warning",
        )
    if rerank_top_score < withhold_t:
        return GateDecisionResult(
            gate_decision="withhold",
            rerank_top_score=rerank_top_score,
            reason=f"rerank_top_score {rerank_top_score:.2f} < withhold threshold {withhold_t:.2f}",
        )
    if rerank_top_score < pass_t:
        return GateDecisionResult(
            gate_decision="hitl",
            rerank_top_score=rerank_top_score,
            reason=(
                f"rerank_top_score {rerank_top_score:.2f} in [{withhold_t:.2f}, "
                f"{pass_t:.2f}) — CO review required"
            ),
        )
    return GateDecisionResult(
        gate_decision="pass",
        rerank_top_score=rerank_top_score,
        reason=f"rerank_top_score {rerank_top_score:.2f} >= pass threshold {pass_t:.2f}",
    )
