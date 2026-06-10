"""One-directional ratchet — per docs/specs/m2-grounded-retrieval/eval-harness.md section 4.1.

The ratchet computes the effective per-PR threshold for each RAGAS metric:

    effective_threshold = max(absolute_floor, main_last_green - 2pp)

If main_last_green is null (bootstrap; baseline_main.json has no stamped
numbers yet), fall back to absolute_floor only. After D3 merges, the
post-merge CI run stamps real baseline numbers.

Gating contract:
  - Faithfulness, Answer Relevancy, Context Precision, Context Recall:
        FAIL if current < effective_threshold (any one is enough).
  - Citation validity rate:  FAIL if rate < 1.0 (hard, spec section 6.1).
  - Cross-tenant leak count: FAIL if count > 0 (hard, spec section 6.2).
  - Latency / token regression: NEVER fails. Warnings only (spec section 6.3).

Exit codes:
  0 — all gates pass
  1 — at least one blocking metric below its effective threshold

CLI:
    python -m eval.ratchet \
        --baseline eval/baseline_main.json \
        --current eval/results.json \
        --current-prog eval/programmatic.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Re-stated here to keep ratchet importable without the runner (unit tests
# only need this constant). Source of truth is spec section 4.
ABSOLUTE_FLOORS: dict[str, float] = {
    "faithfulness": 0.85,
    "answer_relevancy": 0.80,
    "context_precision": 0.75,
    "context_recall": 0.80,
}

RATCHET_TOLERANCE_PP = 0.02  # 2 percentage points per spec section 4.1


def effective_threshold(metric: str, baseline_value: float | None) -> float:
    """Compute the per-PR threshold using max(floor, baseline - 2pp).

    `baseline_value` is None when baseline_main.json carries a null stub
    (bootstrap). In that case the floor applies alone.
    """
    floor = ABSOLUTE_FLOORS[metric]
    if baseline_value is None:
        return floor
    return max(floor, baseline_value - RATCHET_TOLERANCE_PP)


def evaluate_metrics(
    current_metrics: dict[str, float],
    baseline_metrics: dict[str, float | None],
) -> tuple[bool, list[dict[str, Any]]]:
    """Evaluate the four RAGAS metrics against effective thresholds.

    Returns (all_pass, per_metric_rows). Each row has the shape expected by
    the PR-comment table formatter in main().
    """
    rows: list[dict[str, Any]] = []
    all_pass = True
    for metric in ABSOLUTE_FLOORS:
        baseline_value = baseline_metrics.get(metric)
        current_value = current_metrics.get(metric)
        threshold = effective_threshold(metric, baseline_value)
        passed = current_value is not None and current_value >= threshold
        if not passed:
            all_pass = False
        rows.append(
            {
                "metric": metric,
                "current": current_value,
                "baseline": baseline_value,
                "floor": ABSOLUTE_FLOORS[metric],
                "threshold": threshold,
                "passed": passed,
            }
        )
    return all_pass, rows


def evaluate_programmatic(
    prog: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]]]:
    """Check the two hard programmatic gates from spec section 6.1 / 6.2.

    Latency/token (section 6.3) is intentionally NOT a gate.
    """
    rows: list[dict[str, Any]] = []
    all_pass = True

    citation_rate = prog.get("citation_validity_rate", 0.0)
    cit_pass = citation_rate >= 1.0
    if not cit_pass:
        all_pass = False
    rows.append(
        {
            "check": "citation_validity_rate",
            "current": citation_rate,
            "threshold": 1.0,
            "passed": cit_pass,
        }
    )

    leak_count = int(prog.get("cross_tenant_leak_count", 0))
    leak_pass = leak_count == 0
    if not leak_pass:
        all_pass = False
    rows.append(
        {
            "check": "cross_tenant_leak_count",
            "current": leak_count,
            "threshold": 0,
            "passed": leak_pass,
        }
    )
    return all_pass, rows


def format_markdown_table(
    metric_rows: list[dict[str, Any]],
    prog_rows: list[dict[str, Any]],
    soft_signals: dict[str, Any] | None,
) -> str:
    """Render a PR-comment-style markdown report. Spec section 7 step 6 surface."""
    lines: list[str] = []
    lines.append("## RAG Eval Gate")
    lines.append("")
    lines.append("### RAGAS metrics (gating)")
    lines.append("| Metric | Current | Baseline | Floor | Threshold | Pass |")
    lines.append("|---|---:|---:|---:|---:|:---:|")
    for r in metric_rows:
        cur = "n/a" if r["current"] is None else f"{r['current']:.3f}"
        base = "null" if r["baseline"] is None else f"{r['baseline']:.3f}"
        lines.append(
            f"| {r['metric']} | {cur} | {base} | {r['floor']:.2f} | "
            f"{r['threshold']:.3f} | {'PASS' if r['passed'] else 'FAIL'} |"
        )
    lines.append("")
    lines.append("### Programmatic checks (gating)")
    lines.append("| Check | Current | Threshold | Pass |")
    lines.append("|---|---:|---:|:---:|")
    for r in prog_rows:
        lines.append(
            f"| {r['check']} | {r['current']} | {r['threshold']} | "
            f"{'PASS' if r['passed'] else 'FAIL'} |"
        )
    lines.append("")
    if soft_signals:
        lines.append("### Soft signals (NOT gating — spec section 6.3)")
        for k, v in soft_signals.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")
    return "\n".join(lines)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--current-prog", type=Path, required=True)
    parser.add_argument(
        "--report-out",
        type=Path,
        default=None,
        help="If set, write the markdown report to this path (for PR comment step).",
    )
    args = parser.parse_args(argv)

    baseline = _load(args.baseline)
    current = _load(args.current)
    prog = _load(args.current_prog)

    baseline_metrics = baseline.get("metrics", {})
    current_metrics = current.get("metrics", {})

    metrics_pass, metric_rows = evaluate_metrics(current_metrics, baseline_metrics)
    prog_pass, prog_rows = evaluate_programmatic(prog)

    soft_signals = {
        "p50_latency_ms": prog.get("p50_latency_ms"),
        "p95_latency_ms": prog.get("p95_latency_ms"),
        "total_tokens": prog.get("total_tokens"),
    }
    report = format_markdown_table(metric_rows, prog_rows, soft_signals)
    print(report)
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(report, encoding="utf-8")

    all_pass = metrics_pass and prog_pass
    if not all_pass:
        print("[ratchet] FAIL: one or more blocking metrics below threshold", file=sys.stderr)
        return 1
    print("[ratchet] PASS: all blocking metrics above threshold", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
