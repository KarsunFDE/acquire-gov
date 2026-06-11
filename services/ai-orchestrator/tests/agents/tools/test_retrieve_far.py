"""P1.2 — retrieve_far_clauses tests (design ref §13.1)."""
from __future__ import annotations

import pytest

from app.agents.tools import retrieve_far as rf_mod
from app.rerank import RerankResult


def _candidate(chunk_id: str, score: float = 0.8) -> dict:
    return {
        "chunk_id": chunk_id,
        "text": f"chunk {chunk_id}",
        "far_part": "15",
        "far_section": "15.204-5",
        "far_clause": None,
        "snapshot_date": "2026-06-09",
        "relevance_score": score,
    }


class _Retriever:
    def __init__(self, docs):
        self.docs = docs

    def invoke(self, _q):
        return self.docs


def _run(monkeypatch, *, docs, rr: RerankResult, tenant="tenant_A"):
    captured = {}

    def _factory(*, tenant_id, vector_weight=1.0, fulltext_weight=1.0):
        captured["tenant_id"] = tenant_id
        return _Retriever(docs)

    monkeypatch.setattr(rf_mod.retrieval, "build_far_retriever", _factory)
    monkeypatch.setattr(rf_mod.rerank, "rerank_only", lambda q, c: rr)
    cfg = {"configurable": {"tenant_id": tenant}}
    result = rf_mod.retrieve_far_clauses.func(  # type: ignore[attr-defined]
        query="far 15.204-5", k=20, config=cfg
    )
    return result, captured


def test_happy_path_returns_evidence(monkeypatch):
    docs = [_candidate("c1"), _candidate("c2")]
    rr = RerankResult(top=docs, top_score=0.8, degraded_mode=False)
    result, captured = _run(monkeypatch, docs=docs, rr=rr)
    assert captured["tenant_id"] == "tenant_A"
    assert [c.chunk_id for c in result.chunks] == ["c1", "c2"]
    assert result.rerank_top_score == 0.8
    assert result.degraded_mode is False


def test_rerank_outage_degraded_passthrough(monkeypatch):
    docs = [_candidate("c1")]
    rr = RerankResult(top=docs, top_score=None, degraded_mode=True)
    result, _ = _run(monkeypatch, docs=docs, rr=rr)
    assert result.rerank_top_score is None
    assert result.degraded_mode is True


def test_missing_tenant_id_in_config_raises_before_mongo(monkeypatch):
    called = {"factory": False}

    def _factory(**kw):
        called["factory"] = True
        raise AssertionError("factory must not be reached")

    monkeypatch.setattr(rf_mod.retrieval, "build_far_retriever", _factory)
    with pytest.raises(KeyError):
        rf_mod.retrieve_far_clauses.func(  # type: ignore[attr-defined]
            query="q", k=20, config={"configurable": {}}
        )
    assert called["factory"] is False


def test_mongo_failure_propagates(monkeypatch):
    class _BoomRetriever:
        def invoke(self, _q):
            raise ConnectionError("mongo down")

    monkeypatch.setattr(
        rf_mod.retrieval, "build_far_retriever",
        lambda **kw: _BoomRetriever(),
    )
    with pytest.raises(ConnectionError):
        rf_mod.retrieve_far_clauses.func(  # type: ignore[attr-defined]
            query="q", k=20, config={"configurable": {"tenant_id": "t"}}
        )
