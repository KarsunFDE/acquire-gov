"""P2.2 — /section/resume endpoint contract tests (design ref §4.2).

The agent resume is mocked at the ``_resume_agent`` seam; status-code mapping,
edited_args validation, and the agent_resume audit row run real. Graph-level
resume mechanics are covered in tests/agents/test_hitl_interrupt_resume.py.
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import audit as audit_mod
from app.agents.schemas import FinalDraftSection
from app.api import resume as resume_mod


def _final(**over: Any) -> FinalDraftSection:
    base: dict[str, Any] = dict(
        outcome="draft_returned",
        section_text="resumed draft",
        section_id="L",
        citations=[],
        gate_decision="hitl",
        requires_human_review=True,
        rerank_top_score=0.45,
        request_id="req-r",
        run_id="sol-1:L:req-1",
    )
    base.update(over)
    return FinalDraftSection(**base)


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    fa = FastAPI()
    fa.state.audit_records = []
    fa.state.resume_calls = []

    def _fake_audit(action: str, tenant_id: str, request_id: str, **kw: Any) -> str:
        fa.state.audit_records.append(
            {"action": action, "tenant_id": tenant_id, "request_id": request_id, **kw}
        )
        return "stub-id"

    monkeypatch.setattr(audit_mod, "write_audit_log", _fake_audit)

    def _fake_resume(body, *, tenant_id, request_id):
        fa.state.resume_calls.append({"body": body, "tenant_id": tenant_id})
        if body.decision == "reject":
            return _final(outcome="withheld", section_text=None,
                          gate_decision="withhold", request_id=request_id), []
        return _final(request_id=request_id), [{"tool_name": "draft_section_text"}]

    monkeypatch.setattr(resume_mod, "_resume_agent", _fake_resume)
    fa.include_router(resume_mod.router)
    return fa


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


HEADERS = {"X-Tenant-ID": "tenant_A", "X-Request-ID": "req-resume-1"}


def test_approve_resumes_to_draft_returned(client: TestClient, app: FastAPI) -> None:
    resp = client.post(
        "/draft-solicitation/section/resume",
        headers=HEADERS,
        json={"run_id": "sol-1:L:req-1", "decision": "approve"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["outcome"] == "draft_returned"
    assert body["run_id"] == "sol-1:L:req-1"
    rows = [r for r in app.state.audit_records if r["action"] == "agent_resume"]
    assert rows and rows[0]["run_id"] == "sol-1:L:req-1"
    assert rows[0]["resume"]["decision"] == "approve"


def test_reject_resumes_to_withheld(client: TestClient) -> None:
    resp = client.post(
        "/draft-solicitation/section/resume",
        headers=HEADERS,
        json={"run_id": "sol-1:L:req-1", "decision": "reject", "reason": "lean corpus"},
    )
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "withheld"


def test_edit_requires_edited_args(client: TestClient) -> None:
    resp = client.post(
        "/draft-solicitation/section/resume",
        headers=HEADERS,
        json={"run_id": "sol-1:L:req-1", "decision": "edit"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "edited_args_required"


def test_edit_with_args_succeeds(client: TestClient, app: FastAPI) -> None:
    resp = client.post(
        "/draft-solicitation/section/resume",
        headers=HEADERS,
        json={"run_id": "sol-1:L:req-1", "decision": "edit",
              "edited_args": {"rerank_top_score": 0.8}},
    )
    assert resp.status_code == 200
    rows = [r for r in app.state.audit_records if r["action"] == "agent_resume"]
    assert rows[0]["resume"]["edited_args_hash"]  # sha256 recorded, not raw


def test_missing_tenant_400(client: TestClient) -> None:
    resp = client.post(
        "/draft-solicitation/section/resume",
        json={"run_id": "sol-1:L:req-1", "decision": "approve"},
    )
    assert resp.status_code == 400


@pytest.mark.parametrize(
    ("exc", "status", "error"),
    [
        (resume_mod.RunNotFound("x"), 404, "run_not_found"),
        (resume_mod.TenantMismatch("x"), 403, "tenant_mismatch"),
        (resume_mod.RunNotPaused("x"), 409, "run_not_paused"),
    ],
)
def test_status_mapping(client: TestClient, monkeypatch, exc, status, error) -> None:
    def _boom(body, *, tenant_id, request_id):
        raise exc

    monkeypatch.setattr(resume_mod, "_resume_agent", _boom)
    resp = client.post(
        "/draft-solicitation/section/resume",
        headers=HEADERS,
        json={"run_id": "sol-1:L:req-1", "decision": "approve"},
    )
    assert resp.status_code == status
    assert resp.json()["error"] == error


def test_decision_payload_mapping() -> None:
    from app.agents.schemas import ResumeSectionRequest

    approve = resume_mod._decision_payload(
        ResumeSectionRequest(run_id="r", decision="approve")
    )
    assert approve == {"decisions": [{"type": "approve"}]}

    edit = resume_mod._decision_payload(
        ResumeSectionRequest(run_id="r", decision="edit",
                             edited_args={"rerank_top_score": 0.9})
    )
    assert edit["decisions"][0]["type"] == "edit"
    assert edit["decisions"][0]["edited_action"]["args"] == {"rerank_top_score": 0.9}

    reject = resume_mod._decision_payload(
        ResumeSectionRequest(run_id="r", decision="reject", reason="no")
    )
    assert reject["decisions"][0] == {"type": "reject", "message": "no"}
