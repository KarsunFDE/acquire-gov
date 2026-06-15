"""P5.1 — M1 eval-metric unit tests (record-only collectors)."""
from __future__ import annotations

from eval.build_m1_fixtures import build
from eval.metrics.agent_run_metrics import (
    compute_hitl_interrupt_recall,
    compute_tool_order_drift,
    compute_withhold_short_circuit_rate,
    levenshtein,
    run_tool_order_drifted,
)
from eval.metrics.critic_metrics import (
    compute_critic_clin_recall,
    compute_critic_false_positive_rate,
    compute_critic_lm_recall,
    compute_critic_set_aside_recall,
)
from eval.run_m1_metrics import collect, to_markdown


# --- agent-run metrics -------------------------------------------------------

_ORDERED = ["retrieve_far_clauses", "compute_gate_decision",
            "draft_section_text", "validate_citations"]
_REORDERED = ["compute_gate_decision", "retrieve_far_clauses",
              "draft_section_text", "validate_citations"]


def test_levenshtein_basics():
    assert levenshtein(_ORDERED, _ORDERED) == 0
    assert levenshtein(_ORDERED, _REORDERED) == 2
    assert levenshtein([], ["a"]) == 1


def test_drift_detection_allows_skipped_optional_tools():
    assert run_tool_order_drifted(_ORDERED) is False           # optional skipped — legal
    assert run_tool_order_drifted(_REORDERED) is True
    full = ["retrieve_far_clauses", "retrieve_related_solicitations",
            "extract_section_requirements", "compute_gate_decision",
            "draft_section_text", "validate_citations"]
    assert run_tool_order_drifted(full) is False


def test_tool_order_drift_rate():
    runs = [{"tool_sequence": _ORDERED}, {"tool_sequence": _REORDERED}]
    out = compute_tool_order_drift(runs)
    assert out["value"] == 0.5
    assert out["runs_measured"] == 2


def test_withhold_short_circuit_rate():
    runs = [
        {"gate_decision": "withhold", "tool_sequence": ["retrieve_far_clauses", "compute_gate_decision"]},
        {"gate_decision": "withhold", "tool_sequence": _ORDERED},      # drafted anyway → failure
        {"gate_decision": "pass", "tool_sequence": _ORDERED},          # not a withhold run
    ]
    out = compute_withhold_short_circuit_rate(runs)
    assert out["value"] == 0.5
    assert out["runs_measured"] == 2


def test_hitl_interrupt_recall():
    runs = [
        {"rerank_top_score": 0.45, "interrupted": True},
        {"rerank_top_score": 0.50, "interrupted": False},  # band miss → recall hit
        {"rerank_top_score": 0.85, "interrupted": False},  # pass band — excluded
        {"rerank_top_score": None, "interrupted": False},  # passthrough — excluded
    ]
    out = compute_hitl_interrupt_recall(runs)
    assert out["value"] == 0.5
    assert out["runs_measured"] == 2


def test_empty_runs_record_null_not_zero():
    """No silent zeros — unmeasured metrics emit value=None."""
    for fn in (compute_tool_order_drift, compute_withhold_short_circuit_rate,
               compute_hitl_interrupt_recall):
        out = fn([])
        assert out["value"] is None
        assert out["runs_measured"] == 0


# --- critic metrics over the committed fixture set ---------------------------


def test_fixture_set_shape():
    fixtures = build()
    kinds = [f["kind"] for f in fixtures]
    assert kinds.count("set_aside_mismatch") == 8
    assert kinds.count("clin_gap") == 6
    assert kinds.count("lm_mismatch") == 6
    assert kinds.count("known_good") == 20
    assert len(fixtures) == 40


def test_programmatic_recalls_are_perfect_on_fixture_set():
    fixtures = build()
    assert compute_critic_set_aside_recall(fixtures)["value"] == 1.0
    assert compute_critic_clin_recall(fixtures)["value"] == 1.0


def test_false_positive_rate_zero_on_known_good():
    fixtures = build()
    out = compute_critic_false_positive_rate(fixtures)
    assert out["value"] == 0.0
    assert out["runs_measured"] == 20


def test_lm_recall_offline_records_null_with_note():
    out = compute_critic_lm_recall(build(), live=False)
    assert out["value"] is None
    assert "Bedrock" in out["note"]


def test_collect_emits_all_seven_and_markdown_renders():
    rows = collect([], build(), live=False)
    assert {r["metric"] for r in rows} == {
        "tool_order_drift", "withhold_short_circuit_rate", "hitl_interrupt_recall",
        "critic_l_m_alignment_recall", "critic_set_aside_recall",
        "critic_clin_recall", "critic_false_positive_rate",
    }
    md = to_markdown(rows)
    assert "record-only" in md
    for r in rows:
        assert r["metric"] in md
