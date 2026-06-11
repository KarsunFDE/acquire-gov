"""REQ-AID-1 — structured drafts: every M1 endpoint's 200 response is
Pydantic-validated against its locked schema (design ref §13.5; P5.2).

The agent/coordinator/critic seams are mocked; what these tests pin is the
BOUNDARY: the JSON each endpoint returns must round-trip through the schema
the wizard + audit consumers were built against. Contract drift fails here
before it reaches a downstream NullPointerException (the Item-4 lesson).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import audit as audit_mod
from app.agents.schemas import (
    CLINCoverageReport,
    Citation,
    ConsistencyReport,
    FinalDraftSection,
    LMAlignmentReport,
    PartIIClauseList,
    PartResult,
    SetAsideConsistencyReport,
    SolicitationDraftBundle,
)

pytestmark = pytest.mark.req_aid_1

HEADERS = {"X-Tenant-ID": "tenant_A", "X-Request-ID": "req-aid1"}


@pytest.fixture(autouse=True)
def _quiet_audit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(audit_mod, "write_audit_log", lambda *a, **k: "id")


def _final(section_id: str = "C") -> FinalDraftSection:
    return FinalDraftSection(
        outcome="draft_returned",
        section_text="text",
        section_id=section_id,  # type: ignore[arg-type]
        citations=[Citation(
            chunk_id="c1", far_part="15", far_section="15.204-5", far_clause=None,
            snapshot_date=date(2026, 6, 9), relevance_score=0.9, text="far text",
        )],
        gate_decision="pass",
        requires_human_review=False,
        rerank_top_score=0.9,
        request_id="req-aid1",
        run_id=f"sol-1:{section_id}:req-aid1",
    )


def test_section_response_is_pydantic_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import draft as draft_mod

    fa = FastAPI()
    monkeypatch.setattr(
        draft_mod, "_run_agent",
        lambda body, query, *, tenant_id, request_id, run_id, co_user_id=None: (
            _final(body.section_id), []
        ),
    )
    fa.include_router(draft_mod.router)
    resp = TestClient(fa).post(
        "/draft-solicitation/section",
        headers=HEADERS,
        json={"section_id": "C", "solicitation_id": "sol-1", "naics": "541512",
              "set_aside": "SDVOSB", "contract_type": "FFP"},
    )
    assert resp.status_code == 200, resp.text
    FinalDraftSection.model_validate(resp.json())  # raises on contract drift


def test_batch_response_is_pydantic_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import batch as batch_mod

    bundle = SolicitationDraftBundle(
        solicitation_id="sol-1",
        parts={
            "I": PartResult(part="I", kind="llm_drafted",
                            sections={"C": _final("C"), "H": _final("H")}),
            "II": PartResult(part="II", kind="programmatic_resolved", sections={
                "I": PartIIClauseList(
                    clauses_by_reference=[], source="far_snapshot_index",
                    snapshot_date=date(2026, 6, 9), resolved_for={},
                )}),
            "III": PartResult(part="III", kind="wizard_provided", sections={"J": []}),
            "IV": PartResult(part="IV", kind="llm_drafted",
                             sections={"L": _final("L"), "M": _final("M")}),
        },
        overall_outcome="batch_completed",
        consistency_report=None,
        pending_interrupts=[],
        request_id="req-aid1",
        batch_run_id="sol-1:batch:req-aid1",
    )
    fa = FastAPI()
    monkeypatch.setattr(
        batch_mod, "_run_coordinator",
        lambda body, *, tenant_id, request_id, batch_run_id: bundle,
    )
    monkeypatch.setattr(batch_mod, "_charge_extra_cost", lambda request, n: None)
    fa.include_router(batch_mod.router)
    resp = TestClient(fa).post(
        "/draft-solicitation/batch",
        headers=HEADERS,
        json={"solicitation_id": "sol-1", "naics": "541512", "set_aside": "SDVOSB",
              "contract_type": "FFP", "agency_supplement": "GSAM",
              "provenances": {"C": None, "H": None, "L": None, "M": None}},
    )
    assert resp.status_code == 200, resp.text
    SolicitationDraftBundle.model_validate(resp.json())


def test_critic_response_is_pydantic_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import critic as critic_mod

    report = ConsistencyReport(
        solicitation_id="sol-1",
        run_id="sol-1:critic:req-aid1",
        lm_alignment=LMAlignmentReport(
            mismatches=[], overall_severity="info",
            model="amazon.nova-lite-v1:0", input_tokens=0, output_tokens=0,
        ),
        set_aside_consistency=SetAsideConsistencyReport(mismatches=[], overall_severity="info"),
        clin_coverage=CLINCoverageReport(gaps=[], overall_severity="info"),
        overall_severity="info",
        blocks_submit=False,
        model_used="amazon.nova-lite-v1:0",
        timestamp=datetime(2026, 6, 11, tzinfo=timezone.utc),
    )
    fa = FastAPI()
    monkeypatch.setattr(
        critic_mod, "_run_critic_agent",
        lambda body, *, tenant_id, request_id: report,
    )
    fa.include_router(critic_mod.router)
    resp = TestClient(fa).post(
        "/draft-solicitation/critic",
        headers=HEADERS,
        json={"solicitation_id": "sol-1", "set_aside": "SDVOSB",
              "sections": {"L": "L text", "M": "M text"}},
    )
    assert resp.status_code == 200, resp.text
    validated = ConsistencyReport.model_validate(resp.json())
    assert validated.blocks_submit is False  # Phase 1 invariant rides the contract
