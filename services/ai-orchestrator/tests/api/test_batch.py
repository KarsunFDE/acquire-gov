"""P3.6 — /batch + /batch/resume endpoint contract tests (design ref §18.2).

Coordinator mocked at the ``_run_coordinator`` / ``_resume_coordinator``
seams; preflight + multi-cost + audit + status mapping run real. Graph-level
fan-out/interrupt/resume mechanics are covered in
tests/agents/coordinator/test_graph.py.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import audit as audit_mod
from app.agents.schemas import (
    FinalDraftSection,
    PartIIClauseList,
    PartResult,
    PendingToolCall,
    SolicitationDraftBundle,
)
from app.api import batch as batch_mod
from app.api import batch_resume as batch_resume_mod


def _final(section_id: str) -> FinalDraftSection:
    return FinalDraftSection(
        outcome="draft_returned",
        section_text=f"{section_id} text",
        section_id=section_id,  # type: ignore[arg-type]
        citations=[],
        gate_decision="pass",
        requires_human_review=False,
        rerank_top_score=0.8,
        request_id="req-b",
        run_id=f"sol-1:{section_id}:req-b",
    )


def _bundle(outcome: str = "batch_completed") -> SolicitationDraftBundle:
    return SolicitationDraftBundle(
        solicitation_id="sol-1",
        parts={
            "I": PartResult(part="I", kind="llm_drafted",
                            sections={"C": _final("C"), "H": _final("H")}),
            "II": PartResult(part="II", kind="programmatic_resolved", sections={
                "I": PartIIClauseList(
                    clauses_by_reference=[], source="far_snapshot_index",
                    snapshot_date=date(2026, 6, 9),
                    resolved_for={"set_aside": "SDVOSB", "contract_type": "FFP",
                                  "agency_supplement": "GSAM"},
                )
            }),
            "III": PartResult(part="III", kind="wizard_provided", sections={"J": []}),
            "IV": PartResult(part="IV", kind="llm_drafted",
                             sections={"L": _final("L"), "M": _final("M")}),
        },
        overall_outcome=outcome,  # type: ignore[arg-type]
        consistency_report=None,
        pending_interrupts=(
            [] if outcome == "batch_completed"
            else [PendingToolCall(tool_name="compute_gate_decision",
                                  args={"part": "IV", "sections": ["L", "M"],
                                        "rerank_top_score": 0.45},
                                  reason="hitl band")]
        ),
        request_id="req-b",
        batch_run_id="sol-1:batch:req-b",
    )


FULL_BODY = {
    "solicitation_id": "sol-1",
    "naics": "541512",
    "set_aside": "SDVOSB",
    "contract_type": "FFP",
    "agency_supplement": "GSAM",
    "user_constraints_by_section": {"C": "quarterly cadence"},
    "provenances": {"C": None, "H": None, "L": None, "M": None},
    "part_iii_attachments": [
        {"title": "Past performance questionnaire", "date": "2026-06-10",
         "page_count": 4, "filename": "att1.pdf"}
    ],
}

HEADERS = {"X-Tenant-ID": "tenant_A", "X-Request-ID": "req-b"}


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    fa = FastAPI()
    fa.state.audit_records = []
    fa.state.coordinator_calls = []
    fa.state.cost_charges = []

    def _fake_audit(action: str, tenant_id: str, request_id: str, **kw: Any) -> str:
        fa.state.audit_records.append(
            {"action": action, "tenant_id": tenant_id, "request_id": request_id, **kw}
        )
        return "stub-id"

    monkeypatch.setattr(audit_mod, "write_audit_log", _fake_audit)

    def _fake_run(body, *, tenant_id, request_id, batch_run_id):
        fa.state.coordinator_calls.append(
            {"body": body, "tenant_id": tenant_id, "batch_run_id": batch_run_id}
        )
        return _bundle()

    monkeypatch.setattr(batch_mod, "_run_coordinator", _fake_run)
    monkeypatch.setattr(
        batch_mod, "_charge_extra_cost",
        lambda request, n: fa.state.cost_charges.append(n),
    )

    def _fake_resume(body, *, tenant_id, request_id):
        return _bundle()

    monkeypatch.setattr(batch_resume_mod, "_resume_coordinator", _fake_resume)

    fa.include_router(batch_mod.router)
    fa.include_router(batch_resume_mod.router)
    return fa


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_batch_completed_with_four_part_kinds(client: TestClient, app: FastAPI) -> None:
    resp = client.post("/draft-solicitation/batch", headers=HEADERS, json=FULL_BODY)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["overall_outcome"] == "batch_completed"
    assert body["parts"]["I"]["kind"] == "llm_drafted"
    assert body["parts"]["II"]["kind"] == "programmatic_resolved"
    assert body["parts"]["III"]["kind"] == "wizard_provided"
    assert body["parts"]["IV"]["kind"] == "llm_drafted"
    assert body["batch_run_id"] == "sol-1:batch:req-b"


def test_batch_preflight_missing_agency_supplement_422(client: TestClient, app: FastAPI) -> None:
    body = {k: v for k, v in FULL_BODY.items() if k != "agency_supplement"}
    resp = client.post("/draft-solicitation/batch", headers=HEADERS, json=body)
    assert resp.status_code == 422
    assert "agency_supplement" in resp.json()["missing_required"]
    assert app.state.coordinator_calls == []  # no spend


def test_batch_all_provenances_owned_422(client: TestClient) -> None:
    body = {**FULL_BODY, "provenances": {"C": "human", "H": "human",
                                          "L": "human", "M": "human"}}
    resp = client.post("/draft-solicitation/batch", headers=HEADERS, json=body)
    assert resp.status_code == 422
    assert "at_least_one_null_provenance" in resp.json()["missing_required"]


def test_batch_multi_cost_charged_per_part(client: TestClient, app: FastAPI) -> None:
    resp = client.post("/draft-solicitation/batch", headers=HEADERS, json=FULL_BODY)
    assert resp.status_code == 200
    assert app.state.cost_charges == [2]  # Parts I + IV planned
    row = next(r for r in app.state.audit_records
               if r["action"] == "batch_coordinator_run")
    assert row["batch"]["rate_limit_cost"] == 2
    assert sorted(row["batch"]["parts_planned"]) == ["I", "IV"]


def test_batch_single_part_costs_one(client: TestClient, app: FastAPI) -> None:
    body = {**FULL_BODY, "provenances": {"C": "human", "H": "human",
                                          "L": None, "M": None}}
    resp = client.post("/draft-solicitation/batch", headers=HEADERS, json=body)
    assert resp.status_code == 200
    assert app.state.cost_charges == [1]


def test_batch_audit_row_sections_breakdown(client: TestClient, app: FastAPI) -> None:
    client.post("/draft-solicitation/batch", headers=HEADERS, json=FULL_BODY)
    row = next(r for r in app.state.audit_records
               if r["action"] == "batch_coordinator_run")
    assert sorted(row["batch"]["sections_drafted"]) == ["C", "H", "L", "M"]
    assert row["outcome"] == "batch_completed"


def test_batch_interrupted_bundle_passthrough(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        batch_mod, "_run_coordinator",
        lambda body, *, tenant_id, request_id, batch_run_id: _bundle("batch_interrupted"),
    )
    resp = client.post("/draft-solicitation/batch", headers=HEADERS, json=FULL_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_outcome"] == "batch_interrupted"
    assert len(body["pending_interrupts"]) == 1
    assert body["consistency_report"] is None


def test_batch_coordinator_failure_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(body, *, tenant_id, request_id, batch_run_id):
        raise RuntimeError("graph exploded")

    monkeypatch.setattr(batch_mod, "_run_coordinator", _boom)
    resp = client.post("/draft-solicitation/batch", headers=HEADERS, json=FULL_BODY)
    assert resp.status_code == 500
    assert resp.json()["error"] == "coordinator_failure"


# ---------------------------------------------------------------------------
# /batch/resume
# ---------------------------------------------------------------------------


def test_batch_resume_completes(client: TestClient, app: FastAPI) -> None:
    resp = client.post(
        "/draft-solicitation/batch/resume",
        headers=HEADERS,
        json={"batch_run_id": "sol-1:batch:req-b",
              "decisions": [{"section_id": "L", "decision": "approve"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["overall_outcome"] == "batch_completed"
    rows = [r for r in app.state.audit_records if r["action"] == "batch_resume"]
    assert rows and rows[0]["resume"]["decisions"][0]["section_id"] == "L"


def test_batch_resume_edit_requires_args(client: TestClient) -> None:
    resp = client.post(
        "/draft-solicitation/batch/resume",
        headers=HEADERS,
        json={"batch_run_id": "sol-1:batch:req-b",
              "decisions": [{"section_id": "L", "decision": "edit"}]},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "edited_args_required"


@pytest.mark.parametrize(
    ("exc", "status", "error"),
    [
        (batch_resume_mod.BatchRunNotFound("x"), 404, "batch_run_not_found"),
        (batch_resume_mod.TenantMismatch("x"), 403, "tenant_mismatch"),
        (batch_resume_mod.BatchRunNotPaused("x"), 409, "batch_run_not_paused"),
        (batch_resume_mod.DecisionCountMismatch("x"), 422, "decision_count_mismatch"),
    ],
)
def test_batch_resume_status_mapping(
    client: TestClient, monkeypatch, exc, status, error
) -> None:
    def _boom(body, *, tenant_id, request_id):
        raise exc

    monkeypatch.setattr(batch_resume_mod, "_resume_coordinator", _boom)
    resp = client.post(
        "/draft-solicitation/batch/resume",
        headers=HEADERS,
        json={"batch_run_id": "sol-1:batch:req-b",
              "decisions": [{"section_id": "L", "decision": "approve"}]},
    )
    assert resp.status_code == status
    assert resp.json()["error"] == error
