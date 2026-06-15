"""``POST /draft-solicitation/critic`` — standalone Step 12 consistency check.

Design ref §18.2 (ADR-0013 D6.2). Standalone path: L and M may be hand-typed,
so the LLM semantic check is the only alignment surface (ADR-0014 D5).
Phase 1 invariant enforced at the boundary: ``blocks_submit`` is ALWAYS False
and ``overall_severity`` is clamped to warn regardless of what the agent
emits — authority over accuracy.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app import audit as audit_mod
from app import config
from app.agents.schemas import (
    CLINCoverageReport,
    ConsistencyReport,
    CriticRequest,
    LMAlignmentReport,
    SetAsideConsistencyReport,
)

# KNOWN ISSUE (2026-06-12): Nova Lite loops on the critic harness — it re-emits
# the same three tool calls every turn and never produces the final report.
# CRITIC_RECURSION_LIMIT bounds the spend; this caveat rides on the skipped
# report so the wizard tells the CO to review manually.
CRITIC_SKIP_REASON = (
    "Consistency critic did not complete (known issue: critic model loops; "
    "run bounded by CRITIC_RECURSION_LIMIT). No automated L/M, set-aside, or "
    "CLIN checks were performed - review these sections manually before "
    "publishing."
)


def _skipped_report(solicitation_id: str, run_id: str) -> ConsistencyReport:
    """Warn-only placeholder when the critic agent fails (see CRITIC_SKIP_REASON)."""
    return ConsistencyReport(
        solicitation_id=solicitation_id,
        run_id=run_id,
        lm_alignment=LMAlignmentReport(
            mismatches=[], overall_severity="info",
            model="critic_skipped", input_tokens=0, output_tokens=0,
        ),
        set_aside_consistency=SetAsideConsistencyReport(
            mismatches=[], overall_severity="info",
        ),
        clin_coverage=CLINCoverageReport(gaps=[], overall_severity="info"),
        overall_severity="warn",
        blocks_submit=False,
        model_used=None,
        timestamp=datetime.now(timezone.utc),
        critic_skipped=True,
        skip_reason=CRITIC_SKIP_REASON,
    )

log = logging.getLogger("ai-orchestrator.critic")

router = APIRouter(prefix="/draft-solicitation", tags=["draft"])


def _audit_safe(**kwargs: object) -> None:
    try:
        audit_mod.write_audit_log(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover
        log.error("audit write failed: %s", exc)


def clamp_phase1(report: ConsistencyReport) -> ConsistencyReport:
    """Boundary enforcement of the warn-only invariant (ADR-0013 D5)."""
    update: dict = {"blocks_submit": False}
    if report.overall_severity == "fail":
        update["overall_severity"] = "warn"
    return report.model_copy(update=update)


def _critic_user_message(body: CriticRequest, run_id: str) -> str:
    sections = "\n\n".join(
        f"=== SECTION {sid} ===\n{text}"
        for sid, text in sorted(body.sections.items())
        if text
    ) or "(no sections provided)"
    missing = sorted(s for s, t in body.sections.items() if not t)
    return (
        f"Run context: solicitation_id={body.solicitation_id} run_id={run_id} "
        f"timestamp={datetime.now(timezone.utc).isoformat()}\n"
        f"set_aside: {body.set_aside or '(none)'}\n"
        f"Sections missing/empty: {', '.join(missing) or '(none)'}\n\n"
        f"{sections}"
    )


def _run_critic_agent(
    body: CriticRequest, *, tenant_id: str, request_id: str
) -> ConsistencyReport:
    """Build + invoke the critic agent. Tests monkeypatch this seam."""
    from app.agents.critic.builder import build_consistency_critic_agent  # noqa: PLC0415

    run_id = f"{body.solicitation_id}:critic:{request_id}"
    agent = build_consistency_critic_agent()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": _critic_user_message(body, run_id)}]},
        config={
            "recursion_limit": config.CRITIC_RECURSION_LIMIT,
            "configurable": {"tenant_id": tenant_id},
            "tags": ["m1", "consistency-critic", "standalone"],
            "metadata": {
                "request_id": request_id,
                "solicitation_id": body.solicitation_id,
                "tenant_id": tenant_id,
            },
        },
    )
    report: ConsistencyReport = result["structured_response"]
    return report.model_copy(update={"run_id": run_id,
                                     "solicitation_id": body.solicitation_id,
                                     "model_used": config.BEDROCK_CRITIC_MODEL})


@router.post("/critic")
async def run_critic(
    request: Request,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> JSONResponse:
    request_id = x_request_id or str(uuid.uuid4())

    if not x_tenant_id:
        return JSONResponse(
            status_code=400,
            content={"error": "tenant_id_required", "request_id": request_id},
        )

    raw_body = await request.json()
    try:
        body = CriticRequest.model_validate(raw_body)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=422,
            content={"error": "invalid_request", "details": str(exc),
                     "request_id": request_id},
        )

    try:
        report = clamp_phase1(
            _run_critic_agent(body, tenant_id=x_tenant_id, request_id=request_id)
        )
    except Exception as exc:  # noqa: BLE001
        # Known issue: degrade to a skipped report with an explicit
        # review-manually caveat instead of 500ing the wizard (warn-only
        # critic must never block the flow).
        log.error("critic agent failed: %s; returning critic_skipped report", exc)
        report = _skipped_report(
            body.solicitation_id,
            f"{body.solicitation_id}:critic:{request_id}",
        )

    _audit_safe(
        action="consistency_critic",
        tenant_id=x_tenant_id,
        request_id=request_id,
        outcome=report.overall_severity,
        run_id=report.run_id,
        actor={"user_id": x_user_id, "role": None, "session_id": None},
        batch_run_id=None,  # standalone path (design ref §18.7)
        consistency_report_hash=hashlib.sha256(
            report.model_dump_json().encode("utf-8")
        ).hexdigest(),
        overall_severity=report.overall_severity,
        blocks_submit=False,
        critic_skipped=report.critic_skipped,
    )

    return JSONResponse(status_code=200, content=report.model_dump(mode="json"))
