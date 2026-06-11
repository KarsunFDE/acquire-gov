"""M1 eval-metric aggregator (Phase 5 — RECORD-ONLY).

Emits the 7 M1 metrics into ``eval/results/m1_metrics.json`` plus a markdown
table for ``$GITHUB_STEP_SUMMARY``. No thresholds are enforced — Phase 1.5
flips them to gating after the baseline measurement (ADR-0013 D5 rationale).

Inputs:
- ``--runs``: optional JSONL of agent-run records (tool_sequence /
  gate_decision / rerank_top_score / interrupted) harvested from audit rows
  or LangSmith traces. Absent → the three agent-run metrics record null.
- ``--fixtures``: critic fixture set (default eval/fixtures/m1_critic_fixtures.jsonl).
- ``--live``: also run the LLM-backed L↔M recall (needs Bedrock creds).

Run: ``python -m eval.run_m1_metrics --out eval/results/m1_metrics.json``
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from eval.metrics.agent_run_metrics import (
    compute_hitl_interrupt_recall,
    compute_tool_order_drift,
    compute_withhold_short_circuit_rate,
)
from eval.metrics.critic_metrics import (
    compute_critic_clin_recall,
    compute_critic_false_positive_rate,
    compute_critic_lm_recall,
    compute_critic_set_aside_recall,
)

_PHASE_15_TARGETS = {
    "tool_order_drift": "< 0.10",
    "withhold_short_circuit_rate": "> 0.90",
    "hitl_interrupt_recall": "= 1.00",
    "critic_l_m_alignment_recall": ">= 0.85",
    "critic_set_aside_recall": "= 1.00",
    "critic_clin_recall": "= 1.00",
    "critic_false_positive_rate": "< 0.10",
}


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def collect(runs: list[dict], fixtures: list[dict], *, live: bool) -> list[dict]:
    return [
        compute_tool_order_drift(runs),
        compute_withhold_short_circuit_rate(runs),
        compute_hitl_interrupt_recall(runs),
        compute_critic_lm_recall(fixtures, live=live),
        compute_critic_set_aside_recall(fixtures),
        compute_critic_clin_recall(fixtures),
        compute_critic_false_positive_rate(fixtures),
    ]


def to_markdown(rows: list[dict]) -> str:
    lines = [
        "## M1 eval metrics (record-only — Phase 1.5 flips thresholds to gating)",
        "",
        "| metric | value | runs measured | Phase 1.5 target |",
        "|---|---|---|---|",
    ]
    for r in rows:
        value = "—（not measured）" if r["value"] is None else f"{r['value']:.3f}"
        value = value.replace("（not measured）", " (not measured)")
        lines.append(
            f"| {r['metric']} | {value} | {r['runs_measured']} | "
            f"{_PHASE_15_TARGETS[r['metric']]} |"
        )
    lines.append("")
    lines.append(
        "_Record-only per ADR-0013 D5: no precision baseline yet — imposing "
        "recall floors before measuring precision contradicts the warn-only "
        "rationale. Phase 1.5 PR flips these to CI-gating._"
    )
    return "\n".join(lines)


def main() -> int:
    here = Path(__file__).parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, default=here / "results" / "m1_agent_runs.jsonl")
    parser.add_argument("--fixtures", type=Path, default=here / "fixtures" / "m1_critic_fixtures.jsonl")
    parser.add_argument("--out", type=Path, default=here / "results" / "m1_metrics.json")
    parser.add_argument("--live", action="store_true",
                        help="run the LLM-backed L<->M recall (needs Bedrock creds)")
    args = parser.parse_args()

    live = args.live and bool(
        os.environ.get("AWS_BEARER_TOKEN_BEDROCK") or os.environ.get("AWS_ACCESS_KEY_ID")
    )
    runs = _load_jsonl(args.runs)
    fixtures = _load_jsonl(args.fixtures)
    rows = collect(runs, fixtures, live=live)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"metrics": rows}, indent=2), encoding="utf-8")
    md = to_markdown(rows)
    args.out.with_suffix(".md").write_text(md, encoding="utf-8")
    print(md)
    return 0  # ALWAYS 0 in Phase 1 — record-only


if __name__ == "__main__":
    raise SystemExit(main())
