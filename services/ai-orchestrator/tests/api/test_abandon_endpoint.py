"""P2.3 — /section/abandon endpoint + sweeper tests (design ref §4.3, §6.3)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import audit as audit_mod
from app import config
from app import sweeper as sweeper_mod
from app.api import abandon as abandon_mod


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    fa = FastAPI()
    fa.state.audit_records = []
    fa.state.marked = []

    def _fake_audit(action: str, tenant_id: str, request_id: str, **kw: Any) -> str:
        fa.state.audit_records.append(
            {"action": action, "tenant_id": tenant_id, "request_id": request_id, **kw}
        )
        return "stub-id"

    monkeypatch.setattr(audit_mod, "write_audit_log", _fake_audit)

    def _fake_mark(run_id: str) -> int:
        fa.state.marked.append(run_id)
        return 0 if run_id == "ghost" else 2

    monkeypatch.setattr(abandon_mod, "mark_abandoned", _fake_mark)
    fa.include_router(abandon_mod.router)
    return fa


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


HEADERS = {"X-Tenant-ID": "tenant_A", "X-Request-ID": "req-ab-1"}


def test_abandon_marks_and_audits(client: TestClient, app: FastAPI) -> None:
    resp = client.post(
        "/draft-solicitation/section/abandon",
        headers=HEADERS,
        json={"run_id": "sol-1:L:req-1", "reason": "typing manually"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert app.state.marked == ["sol-1:L:req-1"]
    rows = [r for r in app.state.audit_records if r["action"] == "agent_abandon"]
    assert rows and rows[0]["outcome"] == "abandoned"
    assert rows[0]["abandon"]["reason_hash"]  # hashed, never raw


def test_abandon_unknown_run_404(client: TestClient) -> None:
    resp = client.post(
        "/draft-solicitation/section/abandon",
        headers=HEADERS,
        json={"run_id": "ghost"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "run_not_found"


def test_abandon_missing_tenant_400(client: TestClient) -> None:
    resp = client.post(
        "/draft-solicitation/section/abandon", json={"run_id": "sol-1:L:req-1"}
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Sweeper (forced clock — no Mongo)
# ---------------------------------------------------------------------------


class _FakeUpdateResult:
    def __init__(self, matched: int) -> None:
        self.matched_count = matched


class _FakeCheckpointCollection:
    """Minimal stand-in for the langgraph checkpoint collection."""

    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs
        self.updates: list[tuple[dict, dict]] = []

    def find(self, fltr: dict):
        id_cut = fltr.get("_id", {}).get("$lt")
        out = []
        for d in self.docs:
            if id_cut is not None and not (d["_id"] < id_cut):
                continue
            if fltr.get("abandoned", {}).get("$ne") is True and d.get("abandoned") is True:
                continue
            out.append(d)
        return out

    def update_many(self, fltr: dict, update: dict):
        self.updates.append((fltr, update))
        matched = 0
        for d in self.docs:
            if d.get("thread_id") == fltr.get("thread_id"):
                d.update(update["$set"])
                matched += 1
        return _FakeUpdateResult(matched)


def _oid_at(dt: datetime):
    from bson import ObjectId

    return ObjectId.from_datetime(dt)


def test_sweeper_marks_only_stale_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)
    old = now - timedelta(days=config.AGENT_ORPHAN_AGE_DAYS + 5)
    fresh = now - timedelta(days=1)

    coll = _FakeCheckpointCollection([
        {"_id": _oid_at(old), "thread_id": "sol-1:L:stale"},
        {"_id": _oid_at(fresh), "thread_id": "sol-1:C:fresh"},
        {"_id": _oid_at(old), "thread_id": "sol-1:M:already", "abandoned": True},
    ])
    audited: list[dict] = []
    monkeypatch.setattr(sweeper_mod, "_checkpoint_collection", lambda: coll)
    monkeypatch.setattr(sweeper_mod, "_now", lambda: now)
    monkeypatch.setattr(
        audit_mod, "write_audit_log",
        lambda action, tenant_id, request_id, **kw: audited.append(
            {"action": action, **kw}
        ) or "id",
    )

    marked = sweeper_mod.sweep_once()

    assert marked == 1
    stale_doc = next(d for d in coll.docs if d["thread_id"] == "sol-1:L:stale")
    assert stale_doc["abandoned"] is True
    fresh_doc = next(d for d in coll.docs if d["thread_id"] == "sol-1:C:fresh")
    assert "abandoned" not in fresh_doc
    assert audited and audited[0]["action"] == "agent_orphan_swept"
    assert audited[0]["run_id"] == "sol-1:L:stale"


def test_sweeper_marks_never_deletes(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)
    old = now - timedelta(days=config.AGENT_ORPHAN_AGE_DAYS + 5)
    coll = _FakeCheckpointCollection([
        {"_id": _oid_at(old), "thread_id": "sol-9:L:stale"},
    ])
    monkeypatch.setattr(sweeper_mod, "_checkpoint_collection", lambda: coll)
    monkeypatch.setattr(sweeper_mod, "_now", lambda: now)
    monkeypatch.setattr(
        audit_mod, "write_audit_log", lambda *a, **k: "id"
    )

    sweeper_mod.sweep_once()

    assert len(coll.docs) == 1  # marked, not deleted
    assert all("$set" in u[1] for u in coll.updates)


def test_mark_abandoned_returns_matched_count(monkeypatch: pytest.MonkeyPatch) -> None:
    coll = _FakeCheckpointCollection([
        {"_id": _oid_at(datetime.now(timezone.utc)), "thread_id": "sol-2:L:r"},
        {"_id": _oid_at(datetime.now(timezone.utc)), "thread_id": "sol-2:L:r"},
    ])
    monkeypatch.setattr(sweeper_mod, "_checkpoint_collection", lambda: coll)
    assert sweeper_mod.mark_abandoned("sol-2:L:r") == 2
    assert all(d["abandoned"] is True for d in coll.docs)
