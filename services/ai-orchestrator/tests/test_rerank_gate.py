"""C6 — Amazon Rerank 1.0 wiring + threshold gate.

Spec: docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §3 stage 7-8, §11 region pin.
ADR: ADR-0007 D2-D3 (threshold table, reference impl).

Covers:
  - Region pin to us-west-2 (spec §11).
  - Stub-fallback path returns ("pass", top-5) when no client.
  - Real path calls bedrock-agent-runtime.rerank with correct ARN.
  - Threshold gate branches: pass / hitl / withhold.
  - Empty candidates → withhold (spec §3 stage 8).
  - Bedrock failure → stub fallback.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import re

import pytest

from app import config, rerank


def _candidates(n: int = 6) -> list[dict]:
    return [
        {"chunk_id": f"c{i}", "text": f"chunk text {i}", "tenant_id": "tenant_A"}
        for i in range(n)
    ]


# --- Stub fallback ---------------------------------------------------------

def test_rerank_stub_when_no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rerank, "_get_rerank_client", lambda: None)
    decision, top = rerank.rerank_and_gate("query", _candidates(6))
    assert decision == "pass"  # stub mock score 0.7 >= 0.5 hitl threshold
    assert len(top) == config.RERANK_TOP_N
    assert all(c["relevance_score"] == 0.7 for c in top)


def test_rerank_empty_candidates_returns_withhold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §3 stage 8: top score absent (empty) → withhold."""
    monkeypatch.setattr(rerank, "_get_rerank_client", lambda: None)
    decision, top = rerank.rerank_and_gate("query", [])
    assert decision == "withhold"
    assert top == []


# --- Threshold gate branches (mocked rerank client) ------------------------

def _mock_rerank_response(scores: list[float]) -> dict:
    """Build a bedrock-agent-runtime.rerank response with given scores.

    Returns results in index-aligned form like the real API.
    """
    return {
        "results": [
            {"index": i, "relevanceScore": s}
            for i, s in enumerate(scores)
        ]
    }


def test_gate_pass_when_top_above_hitl_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.rerank.return_value = _mock_rerank_response([0.85, 0.6, 0.55, 0.5, 0.45])
    monkeypatch.setattr(rerank, "_get_rerank_client", lambda: client)

    decision, top = rerank.rerank_and_gate("query", _candidates(6))
    assert decision == "pass"
    assert top[0]["relevance_score"] == 0.85
    assert len(top) == 5


def test_gate_hitl_when_top_between_thresholds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.rerank.return_value = _mock_rerank_response([0.4, 0.35, 0.32, 0.31, 0.3])
    monkeypatch.setattr(rerank, "_get_rerank_client", lambda: client)

    decision, top = rerank.rerank_and_gate("query", _candidates(6))
    assert decision == "hitl"
    assert top[0]["relevance_score"] == 0.4


def test_gate_withhold_when_top_below_withhold_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.rerank.return_value = _mock_rerank_response([0.2, 0.15, 0.1, 0.05, 0.01])
    monkeypatch.setattr(rerank, "_get_rerank_client", lambda: client)

    decision, top = rerank.rerank_and_gate("query", _candidates(6))
    assert decision == "withhold"
    assert top == []  # withhold returns no citations


# --- Real path call inspection ---------------------------------------------

def test_real_path_invokes_with_correct_model_arn_and_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §11: Rerank model ARN is the us-west-2 pinned one."""
    client = MagicMock()
    client.rerank.return_value = _mock_rerank_response([0.9])
    monkeypatch.setattr(rerank, "_get_rerank_client", lambda: client)

    rerank.rerank_and_gate("query", _candidates(3))
    call_kwargs = client.rerank.call_args.kwargs
    rerank_config = (
        call_kwargs["rerankingConfiguration"]
        ["bedrockRerankingConfiguration"]
    )
    assert (
        rerank_config["modelConfiguration"]["modelArn"]
        == config.BEDROCK_RERANK_MODEL_ARN
    )
    assert rerank_config["numberOfResults"] == config.RERANK_TOP_N
    assert "us-west-2" in config.BEDROCK_RERANK_MODEL_ARN
    assert config.BEDROCK_RERANK_REGION == "us-west-2"


def test_client_construction_pins_us_west_2(monkeypatch: pytest.MonkeyPatch) -> None:
    """Client init must pass region_name=us-west-2 (ADR-0005 D2)."""
    rerank._client = None  # force re-init
    captured: dict = {}

    def fake_boto_client(service: str, **kwargs: object) -> MagicMock:
        captured["service"] = service
        captured["region_name"] = kwargs.get("region_name")
        return MagicMock()

    monkeypatch.setattr(rerank.boto3, "client", fake_boto_client)
    monkeypatch.setattr(rerank, "_BOTO_AVAILABLE", True)
    rerank._get_rerank_client()
    assert captured["service"] == "bedrock-agent-runtime"
    assert captured["region_name"] == "us-west-2"
    rerank._client = None  # cleanup for other tests


# --- Failure fallback ------------------------------------------------------

def test_bedrock_failure_falls_back_to_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    from botocore.exceptions import ClientError
    client = MagicMock()
    client.rerank.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "x"}}, "Rerank"
    )
    monkeypatch.setattr(rerank, "_get_rerank_client", lambda: client)

    decision, top = rerank.rerank_and_gate("query", _candidates(6))
    # Stub returns score 0.7 → pass.
    assert decision == "pass"
    assert len(top) == config.RERANK_TOP_N


# --- Custom-threshold override --------------------------------------------

def test_threshold_overrides_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.rerank.return_value = _mock_rerank_response([0.6])
    monkeypatch.setattr(rerank, "_get_rerank_client", lambda: client)

    # With default thresholds (0.5 hitl), 0.6 → pass.
    decision, _ = rerank.rerank_and_gate("query", _candidates(2))
    assert decision == "pass"

    # Raise hitl threshold above the score → hitl.
    client.rerank.return_value = _mock_rerank_response([0.6])
    decision, _ = rerank.rerank_and_gate(
        "query", _candidates(2), withhold_threshold=0.3, hitl_threshold=0.7
    )
    assert decision == "hitl"


# --- Audit-skeleton import-only smoke test --------------------------------

def test_audit_skeleton_importable_and_callable() -> None:
    """C6 skeleton: rerank.py imports write_audit_log; verify call shape."""
    from app.audit import write_audit_log
    result = write_audit_log(
        "retrieval_only",
        tenant_id="tenant_A",
        request_id="req-123",
        gate_decision="pass",
    )
    assert isinstance(result, str)
    # File fallback returns a path carrying the request_id; a live Mongo
    # (MONGO_URI set, e.g. mongo-gated local runs) returns the inserted
    # ObjectId hex instead — accept both.
    assert "req-123" in result or re.fullmatch(r"[0-9a-f]{24}", result)
