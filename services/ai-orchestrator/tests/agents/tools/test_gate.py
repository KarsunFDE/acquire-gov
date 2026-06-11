"""P1.2 — compute_gate_decision boundary tests (design ref §13.1)."""
from __future__ import annotations

import pytest

from app import config
from app.agents.tools.gate import compute_gate_decision, gate_thresholds

EPS = 1e-9


def _decide(score):
    return compute_gate_decision.func(rerank_top_score=score)  # type: ignore[attr-defined]


def test_gate_thresholds_reads_config():
    assert gate_thresholds() == (
        config.GATE_WITHHOLD_THRESHOLD,
        config.GATE_PASS_THRESHOLD,
    )


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.0, "withhold"),
        (0.40 - EPS, "withhold"),
        (0.40, "hitl"),                 # withhold_threshold inclusive-lower of hitl band
        (0.55 - 1e-6, "hitl"),
        (0.55, "pass"),                 # pass_threshold inclusive
        (1.0, "pass"),
        (None, "rerank_unavailable_passthrough"),
    ],
)
def test_boundaries(score, expected):
    result = _decide(score)
    assert result.gate_decision == expected
    assert result.rerank_top_score == score
    assert result.reason


def test_result_is_fully_determined_by_input_args():
    """ADR-0012 D6 — the middleware inspects INPUT args; same input must give
    the same decision every time (pure function, no hidden state)."""
    assert _decide(0.48).gate_decision == _decide(0.48).gate_decision == "hitl"
