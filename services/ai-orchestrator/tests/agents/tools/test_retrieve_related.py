"""P1.2 — retrieve_related_solicitations tests (design ref §13.1)."""
from __future__ import annotations

import pytest

from app.agents.tools import retrieve_related as rr_mod


def _doc(sol_id: str, tenant: str = "tenant_A") -> dict:
    return {
        "solicitation_id": sol_id,
        "tenant_id": tenant,
        "title": f"solicitation {sol_id}",
        "naics": "541512",
        "set_aside": "SDVOSB",
        "contract_type": "FFP",
        "award_status": "awarded",
        "snapshot_date": "2026-06-09",
    }


def _run(monkeypatch, docs=None, *, naics=None, set_aside=None, boom=False):
    calls = []

    def _query(tenant_id, n, s, k):
        calls.append({"tenant_id": tenant_id, "naics": n, "set_aside": s, "k": k})
        if boom:
            raise ConnectionError("mongo down")
        return docs or []

    monkeypatch.setattr(rr_mod, "_query_related", _query)
    result = rr_mod.retrieve_related_solicitations.func(  # type: ignore[attr-defined]
        naics=naics, set_aside=set_aside, k=5,
        config={"configurable": {"tenant_id": "tenant_A"}},
    )
    return result, calls


def test_null_args_short_circuit_zero_mongo_cost(monkeypatch):
    result, calls = _run(monkeypatch)
    assert result.count == 0
    assert result.summaries == []
    assert calls == []  # NO Mongo round-trip


def test_naics_filter_returns_summaries(monkeypatch):
    result, calls = _run(monkeypatch, docs=[_doc("sol-9")], naics="541512")
    assert result.count == 1
    assert result.summaries[0].solicitation_id == "sol-9"
    assert calls[0]["tenant_id"] == "tenant_A"


def test_mongo_failure_non_fatal_returns_empty(monkeypatch):
    result, _ = _run(monkeypatch, naics="541512", boom=True)
    assert result.count == 0
    assert result.summaries == []


@pytest.mark.req_rag_3
def test_tenant_id_comes_from_config_not_args(monkeypatch):
    """REQ-RAG-3 — tool reads tenant from RunnableConfig only; tool args have
    no tenant parameter to spoof (extends test_retrieval_tenant_isolation)."""
    _, calls = _run(monkeypatch, docs=[], naics="541512")
    assert calls[0]["tenant_id"] == "tenant_A"
    # the tool signature exposes no tenant_id arg the model could set
    schema = rr_mod.retrieve_related_solicitations.args_schema.model_json_schema()
    assert "tenant_id" not in schema.get("properties", {})
