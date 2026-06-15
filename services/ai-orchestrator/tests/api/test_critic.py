"""P4.4 — /critic endpoint contract tests (ADR-0013 D6.2 + ADR-0014 D5)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import audit as audit_mod
from app.agents.schemas import (
    CLINCoverageReport,
    CLINGap,
    ConsistencyReport,
    LMAlignmentReport,
    SetAsideConsistencyReport,
    SetAsideMismatch,
)
from app.api import critic as critic_mod


def _report(overall: str = "warn") -> ConsistencyReport:
    return ConsistencyReport(
        solicitation_id="sol-1",
        run_id="sol-1:critic:req-c",
        lm_alignment=LMAlignmentReport(
            mismatches=[], overall_severity="info",
            model="amazon.nova-lite-v1:0", input_tokens=10, output_tokens=5,
        ),
        set_aside_consistency=SetAsideConsistencyReport(
            mismatches=[SetAsideMismatch(
                set_aside="SDVOSB", expected_reps=["52.219-27"], actual_reps=[],
                missing=["52.219-27"], extra=[], severity="warn",
            )],
            overall_severity="warn",
        ),
        clin_coverage=CLINCoverageReport(
            gaps=[CLINGap(clin_id="0002", missing_in=["F"], severity="warn")],
            overall_severity="warn",
        ),
        overall_severity=overall,  # type: ignore[arg-type]
        blocks_submit=False,
        model_used="amazon.nova-lite-v1:0",
        timestamp=datetime(2026, 6, 11, tzinfo=timezone.utc),
    )


BODY = {
    "solicitation_id": "sol-1",
    "set_aside": "SDVOSB",
    "sections": {
        "B": "0001 services\nCLIN 0002 surge",
        "C": "covers 0001 and 0002",
        "F": "deliveries for 0001",
        "K": "no reps",
        "L": "Offerors shall ...",
        "M": "The Government will evaluate ...",
    },
}

HEADERS = {"X-Tenant-ID": "tenant_A", "X-Request-ID": "req-c"}


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    fa = FastAPI()
    fa.state.audit_records = []

    def _fake_audit(action: str, tenant_id: str, request_id: str, **kw: Any) -> str:
        fa.state.audit_records.append(
            {"action": action, "tenant_id": tenant_id, "request_id": request_id, **kw}
        )
        return "stub-id"

    monkeypatch.setattr(audit_mod, "write_audit_log", _fake_audit)
    monkeypatch.setattr(
        critic_mod, "_run_critic_agent",
        lambda body, *, tenant_id, request_id: _report(),
    )
    fa.include_router(critic_mod.router)
    return fa


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_known_mismatch_returns_warn_report(client: TestClient, app: FastAPI) -> None:
    resp = client.post("/draft-solicitation/critic", headers=HEADERS, json=BODY)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["overall_severity"] == "warn"
    assert body["set_aside_consistency"]["mismatches"][0]["missing"] == ["52.219-27"]
    assert body["clin_coverage"]["gaps"][0]["clin_id"] == "0002"
    assert body["blocks_submit"] is False
    rows = [r for r in app.state.audit_records if r["action"] == "consistency_critic"]
    assert rows and rows[0]["consistency_report_hash"]
    assert rows[0]["blocks_submit"] is False
    assert rows[0]["batch_run_id"] is None  # standalone path


def test_phase1_clamp_fail_to_warn_and_blocks_submit_false(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even if the agent emits fail/blocks_submit=True, the boundary clamps."""
    rogue = _report("fail").model_copy(update={"blocks_submit": True})
    monkeypatch.setattr(
        critic_mod, "_run_critic_agent",
        lambda body, *, tenant_id, request_id: rogue,
    )
    resp = client.post("/draft-solicitation/critic", headers=HEADERS, json=BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_severity"] == "warn"   # clamped
    assert body["blocks_submit"] is False        # always


def test_missing_tenant_400(client: TestClient) -> None:
    resp = client.post("/draft-solicitation/critic", json=BODY)
    assert resp.status_code == 400


def test_invalid_body_422(client: TestClient) -> None:
    resp = client.post(
        "/draft-solicitation/critic", headers=HEADERS,
        json={"solicitation_id": "sol-1", "sections": {"Z": "nope"}},
    )
    assert resp.status_code == 422


def test_critic_failure_returns_skipped_report(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Known issue (2026-06-12): critic model loops; agent failure degrades to
    a 200 critic_skipped report with a review-manually caveat — the warn-only
    critic must never 500 the wizard."""
    def _boom(body, *, tenant_id, request_id):
        raise RuntimeError("nova outage")

    monkeypatch.setattr(critic_mod, "_run_critic_agent", _boom)
    resp = client.post("/draft-solicitation/critic", headers=HEADERS, json=BODY)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["critic_skipped"] is True
    assert payload["overall_severity"] == "warn"
    assert payload["blocks_submit"] is False
    assert "review" in payload["skip_reason"].lower()
