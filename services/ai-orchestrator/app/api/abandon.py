"""``POST /draft-solicitation/section/abandon`` — orphan-thread cleanup.

Design ref §4.3 (ADR-0012 D8.2). Marks the checkpoint ``abandoned=True``
(same sentinel the sweeper sets); does NOT delete — the sweeper reclaims
after the AGENT_ORPHAN_AGE_DAYS window.
"""
from __future__ import annotations

import hashlib
import logging
import uuid

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app import audit as audit_mod
from app.agents.schemas import AbandonSectionRequest
from app.sweeper import mark_abandoned

log = logging.getLogger("ai-orchestrator.abandon")

router = APIRouter(prefix="/draft-solicitation", tags=["draft"])


def _audit_safe(**kwargs: object) -> None:
    try:
        audit_mod.write_audit_log(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover
        log.error("audit write failed: %s", exc)


@router.post("/section/abandon")
async def abandon_section(
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
        body = AbandonSectionRequest.model_validate(raw_body)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=422,
            content={"error": "invalid_request", "details": str(exc),
                     "request_id": request_id},
        )

    try:
        matched = mark_abandoned(body.run_id)
    except Exception as exc:  # noqa: BLE001
        log.error("abandon failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"error": "mongo_unavailable", "request_id": request_id},
        )

    if matched == 0:
        return JSONResponse(
            status_code=404,
            content={"error": "run_not_found", "request_id": request_id},
        )

    _audit_safe(
        action="agent_abandon",
        tenant_id=x_tenant_id,
        request_id=request_id,
        outcome="abandoned",
        run_id=body.run_id,
        actor={"user_id": x_user_id, "role": None, "session_id": None},
        abandon={
            "reason_hash": (
                hashlib.sha256(body.reason.encode("utf-8")).hexdigest()
                if body.reason else None
            )
        },
    )
    return JSONResponse(status_code=200, content={"ok": True, "request_id": request_id})
