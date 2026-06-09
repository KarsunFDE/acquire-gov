"""Smoke tests — mock HTTP, verify runner orchestration.

Integration of the full eval run against real backends lives in CI
(see .github/workflows/rag-eval-gate.yml) and depends on the pipeline +
corpus agents' deliverables. These smoke tests verify that:

- run_ragas.gather_records calls /retrieve once per entry and lifts the
  fields it claims to
- run_programmatic.run_all coordinates the three checks without crashing
  on an empty eval set
- run_programmatic.check_cross_tenant_fuzz emits N=20 probes and counts
  leaks correctly when the mock leaks
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval import run_programmatic  # noqa: E402
from eval import run_ragas  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload
        self.status_code = 200

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _FakeClient:
    def __init__(self, payload: dict, *_, **__):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, *_args, **_kwargs):
        return _FakeResponse(self._payload)


def _mock_httpx_client(payload: dict):
    """Return a context-manager that patches httpx.Client → FakeClient(payload)."""
    return patch("httpx.Client", lambda *a, **k: _FakeClient(payload))


# --- run_ragas.gather_records ---

@pytest.mark.eval_harness
def test_gather_records_lifts_citations_into_contexts() -> None:
    payload = {
        "outcome": "retrieved",
        "gate_decision": "pass",
        "rerank_top_score": 0.81,
        "request_id": "req-1",
        "citations": [
            {"chunk_id": "c1", "text": "FAR 52.212-4 says contracts...",
             "tenant_id": "agency-test"},
            {"chunk_id": "c2", "text": "Commercial item terms...",
             "tenant_id": "agency-test"},
        ],
    }
    eval_set = [
        {
            "eval_id": "EV-0001",
            "query": "What does FAR 52.212-4 say?",
            "tenant_id": "agency-test",
            "category": "clause-lookup",
            "expected_answer_summary": "FAR 52.212-4 covers commercial-item terms.",
        }
    ]
    with _mock_httpx_client(payload):
        records = run_ragas.gather_records(eval_set, "http://localhost:8000", 5.0)

    assert len(records) == 1
    r = records[0]
    assert r.error is None
    assert r.contexts == [
        "FAR 52.212-4 says contracts...",
        "Commercial item terms...",
    ]
    assert "FAR 52.212-4" in r.answer
    assert r.request_id == "req-1"
    assert r.gate_decision == "pass"


@pytest.mark.eval_harness
def test_gather_records_records_error_on_http_failure() -> None:
    class _BoomClient:
        def __init__(self, *a, **k): ...
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **k): raise RuntimeError("boom")

    with patch("httpx.Client", lambda *a, **k: _BoomClient()):
        records = run_ragas.gather_records(
            [{"eval_id": "EV-1", "query": "x", "tenant_id": "agency-test",
              "category": "clause-lookup", "expected_answer_summary": ""}],
            "http://localhost:8000",
            5.0,
        )
    assert records[0].error is not None
    assert "boom" in records[0].error


# --- run_programmatic ---

@pytest.mark.eval_harness
def test_run_programmatic_empty_eval_set_is_clean(tmp_path: Path) -> None:
    eval_set_path = tmp_path / "empty.jsonl"
    eval_set_path.write_text("", encoding="utf-8")
    baseline_path = tmp_path / "lat-baseline.json"
    baseline_path.write_text(
        json.dumps({"p95_latency_ms": None, "total_tokens": None})
    )

    # Even cross-tenant fuzz hits the endpoint. Mock it to return a clean
    # (no-tenant-id-in-citations) payload — counts as 0 leaks.
    with _mock_httpx_client({"citations": [{"chunk_id": "c1", "text": "x"}]}):
        result = run_programmatic.run_all(eval_set_path, "http://x", baseline_path)
    assert result.citation_validity_rate == 1.0  # vacuously true on empty
    assert result.cross_tenant_leak_count == 0
    assert result.cross_tenant_fuzz_n == run_programmatic.CROSS_TENANT_FUZZ_N


@pytest.mark.eval_harness
def test_cross_tenant_fuzz_detects_leak_when_tenant_id_mismatched() -> None:
    # Payload has a chunk with a foreign tenant_id → must count as a leak.
    leaky_payload = {
        "citations": [
            {"chunk_id": "c-leak", "text": "evil", "tenant_id": "agency-other"}
        ]
    }
    with _mock_httpx_client(leaky_payload):
        leak_count, n, examples = run_programmatic.check_cross_tenant_fuzz(
            "http://x", n=5, seed=42
        )
    assert leak_count == 5  # every probe leaked under this mock
    assert n == 5
    assert all(ex["leaked_tenant_id"] == "agency-other" for ex in examples)


@pytest.mark.eval_harness
def test_cross_tenant_fuzz_clean_when_tenant_id_matches() -> None:
    clean_payload = {
        "citations": [
            {"chunk_id": "c-ok", "text": "fine", "tenant_id": "agency-test"}
        ]
    }
    with _mock_httpx_client(clean_payload):
        leak_count, n, examples = run_programmatic.check_cross_tenant_fuzz(
            "http://x", n=5, seed=42
        )
    assert leak_count == 0
    assert examples == []


@pytest.mark.eval_harness
def test_latency_regression_emits_warning_above_25pct(tmp_path: Path) -> None:
    baseline_path = tmp_path / "lat.json"
    baseline_path.write_text(
        json.dumps({"p95_latency_ms": 1000.0, "total_tokens": 0})
    )
    # 25 samples so quantiles(n=20) succeeds; p95 will be the 19th-of-19
    # interpolation point on a sorted list dominated by 1500.
    lats = [1500.0] * 25
    p50, p95, tokens, warns = run_programmatic.check_latency_token_regression(
        len(lats), lats, baseline_path
    )
    assert p95 > 1000.0
    # +50% latency exceeds the +25% soft-warning threshold.
    assert any("p95 latency regression" in w for w in warns)
