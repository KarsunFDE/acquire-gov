"""Agent-run metrics: tool_order_drift, withhold_short_circuit_rate,
hitl_interrupt_recall (design ref §13.2).

Input shape — one dict per agent run (extracted from audit rows'
``generation.tool_calls`` sub-records or LangSmith traces)::

    {
      "tool_sequence": ["retrieve_far_clauses", "compute_gate_decision", ...],
      "gate_decision": "pass" | "hitl" | "withhold" | "rerank_unavailable_passthrough",
      "rerank_top_score": float | None,
      "interrupted": bool,
    }
"""
from __future__ import annotations

from app.agents.tools.gate import gate_thresholds

# The prompted order (design ref §7.1). Optional tools are skipped legally;
# drift is measured against the subsequence of prompted tools actually used.
PROMPTED_ORDER = [
    "retrieve_far_clauses",
    "retrieve_related_solicitations",
    "extract_section_requirements",
    "compute_gate_decision",
    "draft_section_text",
    "validate_citations",
]


def levenshtein(a: list[str], b: list[str]) -> int:
    """Plain edit distance over tool-name sequences."""
    m, n = len(a), len(b)
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[n]


def run_tool_order_drifted(tool_sequence: list[str]) -> bool:
    """A run drifted when its prompted-tool subsequence isn't in prompted order."""
    observed = [t for t in tool_sequence if t in PROMPTED_ORDER]
    expected = [t for t in PROMPTED_ORDER if t in set(observed)]
    return levenshtein(observed, expected) > 0


def compute_tool_order_drift(runs: list[dict]) -> dict:
    """Fraction of runs whose tool sequence reorders off the prompted order.

    Phase 1.5 threshold: < 0.10."""
    measured = [r for r in runs if r.get("tool_sequence")]
    if not measured:
        return {"metric": "tool_order_drift", "value": None, "runs_measured": 0}
    drifted = sum(1 for r in measured if run_tool_order_drifted(r["tool_sequence"]))
    return {
        "metric": "tool_order_drift",
        "value": drifted / len(measured),
        "runs_measured": len(measured),
    }


def compute_withhold_short_circuit_rate(runs: list[dict]) -> dict:
    """Of withhold-gate runs, fraction that correctly SKIPPED draft_section_text.

    Phase 1.5 threshold: > 0.90."""
    withhold_runs = [r for r in runs if r.get("gate_decision") == "withhold"]
    if not withhold_runs:
        return {"metric": "withhold_short_circuit_rate", "value": None, "runs_measured": 0}
    ok = sum(
        1 for r in withhold_runs
        if "draft_section_text" not in (r.get("tool_sequence") or [])
    )
    return {
        "metric": "withhold_short_circuit_rate",
        "value": ok / len(withhold_runs),
        "runs_measured": len(withhold_runs),
    }


def compute_hitl_interrupt_recall(runs: list[dict]) -> dict:
    """Of hitl-band-score runs, fraction that actually paused.

    Phase 1.5 threshold: = 1.00."""
    withhold_t, pass_t = gate_thresholds()
    band_runs = [
        r for r in runs
        if r.get("rerank_top_score") is not None
        and withhold_t <= r["rerank_top_score"] < pass_t
    ]
    if not band_runs:
        return {"metric": "hitl_interrupt_recall", "value": None, "runs_measured": 0}
    interrupted = sum(1 for r in band_runs if r.get("interrupted"))
    return {
        "metric": "hitl_interrupt_recall",
        "value": interrupted / len(band_runs),
        "runs_measured": len(band_runs),
    }
