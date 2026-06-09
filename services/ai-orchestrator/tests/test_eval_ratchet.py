"""Unit tests for eval.ratchet — one-directional threshold logic (spec section 4.1).

Programmatic gate logic (Checks 1 + 2) and PR-comment rendering also covered.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.ratchet import (  # noqa: E402
    ABSOLUTE_FLOORS,
    RATCHET_TOLERANCE_PP,
    effective_threshold,
    evaluate_metrics,
    evaluate_programmatic,
    format_markdown_table,
    main as ratchet_main,
)


# --- effective_threshold ---

@pytest.mark.eval_harness
def test_effective_threshold_bootstrap_uses_floor() -> None:
    # Null baseline (bootstrap): threshold == floor exactly.
    for metric, floor in ABSOLUTE_FLOORS.items():
        assert effective_threshold(metric, None) == floor


@pytest.mark.eval_harness
def test_effective_threshold_baseline_above_floor_tightens() -> None:
    # Baseline well above floor: threshold = baseline - 2pp.
    threshold = effective_threshold("faithfulness", baseline_value=0.95)
    assert threshold == pytest.approx(0.95 - RATCHET_TOLERANCE_PP)


@pytest.mark.eval_harness
def test_effective_threshold_floor_clamps_when_baseline_drops() -> None:
    # If baseline somehow drops below floor + 2pp, floor still wins.
    threshold = effective_threshold("faithfulness", baseline_value=0.84)
    # 0.84 - 0.02 = 0.82 < floor 0.85 → floor wins.
    assert threshold == 0.85


@pytest.mark.eval_harness
def test_effective_threshold_one_directional_never_relaxes() -> None:
    # Tested invariant: for any baseline >= floor + tolerance, the threshold
    # is always >= floor. This is the "ratchet never decreases without ADR"
    # property restated.
    for metric, floor in ABSOLUTE_FLOORS.items():
        for baseline in [floor, floor + 0.01, floor + 0.1, 1.0]:
            assert effective_threshold(metric, baseline) >= floor


# --- evaluate_metrics ---

@pytest.mark.eval_harness
def test_evaluate_metrics_all_pass_above_floor_bootstrap() -> None:
    current = {
        "faithfulness": 0.90,
        "answer_relevancy": 0.85,
        "context_precision": 0.80,
        "context_recall": 0.85,
    }
    baseline = {k: None for k in ABSOLUTE_FLOORS}
    ok, rows = evaluate_metrics(current, baseline)
    assert ok
    assert all(r["passed"] for r in rows)


@pytest.mark.eval_harness
def test_evaluate_metrics_fail_below_floor() -> None:
    current = {
        "faithfulness": 0.84,  # below floor
        "answer_relevancy": 0.85,
        "context_precision": 0.80,
        "context_recall": 0.85,
    }
    baseline = {k: None for k in ABSOLUTE_FLOORS}
    ok, rows = evaluate_metrics(current, baseline)
    assert not ok
    failing = [r for r in rows if not r["passed"]]
    assert len(failing) == 1
    assert failing[0]["metric"] == "faithfulness"


@pytest.mark.eval_harness
def test_evaluate_metrics_baseline_ratchet_tightens() -> None:
    # Baseline is 0.95; threshold = 0.93. Current 0.92 < 0.93 → fail
    current = {"faithfulness": 0.92, "answer_relevancy": 0.90,
               "context_precision": 0.85, "context_recall": 0.90}
    baseline = {"faithfulness": 0.95, "answer_relevancy": 0.90,
                "context_precision": 0.85, "context_recall": 0.90}
    ok, rows = evaluate_metrics(current, baseline)
    assert not ok
    faith_row = next(r for r in rows if r["metric"] == "faithfulness")
    assert not faith_row["passed"]
    assert faith_row["threshold"] == pytest.approx(0.93)


@pytest.mark.eval_harness
def test_evaluate_metrics_missing_current_fails() -> None:
    current: dict[str, float] = {}
    baseline = {k: None for k in ABSOLUTE_FLOORS}
    ok, _ = evaluate_metrics(current, baseline)
    assert not ok


# --- evaluate_programmatic ---

@pytest.mark.eval_harness
def test_evaluate_programmatic_citation_pass_leak_zero() -> None:
    ok, rows = evaluate_programmatic(
        {"citation_validity_rate": 1.0, "cross_tenant_leak_count": 0}
    )
    assert ok
    assert all(r["passed"] for r in rows)


@pytest.mark.eval_harness
def test_evaluate_programmatic_citation_below_1_fails() -> None:
    ok, _ = evaluate_programmatic(
        {"citation_validity_rate": 0.99, "cross_tenant_leak_count": 0}
    )
    assert not ok


@pytest.mark.eval_harness
def test_evaluate_programmatic_any_leak_fails() -> None:
    ok, _ = evaluate_programmatic(
        {"citation_validity_rate": 1.0, "cross_tenant_leak_count": 1}
    )
    assert not ok


@pytest.mark.eval_harness
def test_evaluate_programmatic_latency_warnings_not_gating() -> None:
    # Spec section 6.3: latency / token regression NEVER blocks.
    # No latency field on the prog payload here at all — ratchet must pass.
    ok, _ = evaluate_programmatic(
        {"citation_validity_rate": 1.0, "cross_tenant_leak_count": 0}
    )
    assert ok


# --- format_markdown_table ---

@pytest.mark.eval_harness
def test_format_markdown_table_includes_pass_fail_marks() -> None:
    metric_rows = [
        {"metric": "faithfulness", "current": 0.90, "baseline": None,
         "floor": 0.85, "threshold": 0.85, "passed": True},
        {"metric": "context_recall", "current": 0.70, "baseline": 0.85,
         "floor": 0.80, "threshold": 0.83, "passed": False},
    ]
    prog_rows = [
        {"check": "citation_validity_rate", "current": 1.0,
         "threshold": 1.0, "passed": True},
        {"check": "cross_tenant_leak_count", "current": 0,
         "threshold": 0, "passed": True},
    ]
    md = format_markdown_table(metric_rows, prog_rows, {"p95_latency_ms": 1234})
    assert "PASS" in md
    assert "FAIL" in md
    assert "context_recall" in md
    assert "Soft signals" in md
    assert "1234" in md


# --- main / CLI ---

@pytest.mark.eval_harness
def test_main_returns_zero_on_all_pass(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    prog = tmp_path / "prog.json"
    baseline.write_text(json.dumps({"metrics": {k: None for k in ABSOLUTE_FLOORS}}))
    current.write_text(
        json.dumps(
            {
                "metrics": {
                    "faithfulness": 0.90,
                    "answer_relevancy": 0.85,
                    "context_precision": 0.80,
                    "context_recall": 0.85,
                }
            }
        )
    )
    prog.write_text(json.dumps({"citation_validity_rate": 1.0, "cross_tenant_leak_count": 0}))

    rc = ratchet_main(
        [
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--current-prog",
            str(prog),
        ]
    )
    assert rc == 0


@pytest.mark.eval_harness
def test_main_returns_one_on_metric_fail(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    prog = tmp_path / "prog.json"
    baseline.write_text(json.dumps({"metrics": {k: None for k in ABSOLUTE_FLOORS}}))
    current.write_text(
        json.dumps(
            {
                "metrics": {
                    "faithfulness": 0.50,  # well below floor
                    "answer_relevancy": 0.85,
                    "context_precision": 0.80,
                    "context_recall": 0.85,
                }
            }
        )
    )
    prog.write_text(json.dumps({"citation_validity_rate": 1.0, "cross_tenant_leak_count": 0}))

    rc = ratchet_main(
        [
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--current-prog",
            str(prog),
        ]
    )
    assert rc == 1


@pytest.mark.eval_harness
def test_main_returns_one_on_leak(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    prog = tmp_path / "prog.json"
    baseline.write_text(json.dumps({"metrics": {k: None for k in ABSOLUTE_FLOORS}}))
    current.write_text(
        json.dumps(
            {
                "metrics": {
                    "faithfulness": 0.90,
                    "answer_relevancy": 0.85,
                    "context_precision": 0.80,
                    "context_recall": 0.85,
                }
            }
        )
    )
    prog.write_text(json.dumps({"citation_validity_rate": 1.0, "cross_tenant_leak_count": 3}))

    rc = ratchet_main(
        [
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--current-prog",
            str(prog),
        ]
    )
    assert rc == 1
