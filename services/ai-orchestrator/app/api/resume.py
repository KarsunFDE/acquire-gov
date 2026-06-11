"""``POST /draft-solicitation/section/resume`` — resume a paused HITL run.

Design ref §4.2 (ADR-0012 D6/D8). The handler reads the run's checkpoint via
the MongoDBSaver singleton, validates tenant + paused state, builds the
``Command(resume={"decisions": [...]})`` payload, and re-invokes the agent
from the checkpoint. Resume rows join the original draft row on ``run_id``.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app import audit as audit_mod
from app import config
from app.agents.schemas import FinalDraftSection, ResumeSectionRequest
from app.citations import CitationVerificationFailed

log = logging.getLogger("ai-orchestrator.resume")

router = APIRouter(prefix="/draft-solicitation", tags=["draft"])


class RunNotFound(Exception):
    pass


class RunNotPaused(Exception):
    pass


class TenantMismatch(Exception):
    pass


def _sha256_or_none(value: object) -> str | None:
    import hashlib
    import json

    if value is None:
        return None
    raw = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _audit_safe(**kwargs: object) -> None:
    try:
        audit_mod.write_audit_log(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover
        log.error("audit write failed: %s", exc)


def _decision_payload(body: ResumeSectionRequest) -> dict:
    """ResumeSectionRequest → HITLResponse dict (design ref §4.2 semantics)."""
    if body.decision == "approve":
        return {"decisions": [{"type": "approve"}]}
    if body.decision == "edit":
        return {
            "decisions": [
                {
                    "type": "edit",
                    "edited_action": {
                        "name": "compute_gate_decision",
                        "args": body.edited_args or {},
                    },
                }
            ]
        }
    return {
        "decisions": [
            {"type": "reject", "message": body.reason or "CO rejected the gate decision"}
        ]
    }


def _resume_agent(
    body: ResumeSectionRequest, *, tenant_id: str, request_id: str
) -> tuple[FinalDraftSection, list]:
    """Read checkpoint → validate → Command(resume=...) → final response.

    Raises RunNotFound / RunNotPaused / TenantMismatch for the status table.
    Tests monkeypatch this seam for handler-contract tests; the real path is
    covered by the graph-level pause/resume integration tests.
    """
    from langgraph.types import Command  # noqa: PLC0415

    from app.agents.builder import build_section_drafter_agent  # noqa: PLC0415
    from app.agents.checkpointer import parse_thread_id  # noqa: PLC0415
    from app.agents.tool_call_capture import ToolCallCapture  # noqa: PLC0415
    from app.api.draft import _interrupted_final  # noqa: PLC0415

    try:
        _, section_id, _ = parse_thread_id(body.run_id)
    except ValueError as exc:
        raise RunNotFound(str(exc)) from exc

    agent = build_section_drafter_agent()
    cfg = {"configurable": {"thread_id": body.run_id, "tenant_id": tenant_id}}

    snapshot = agent.get_state(cfg)
    if snapshot is None or not snapshot.config.get("configurable", {}).get("checkpoint_id"):
        raise RunNotFound(body.run_id)

    # D8.1 — same-tenant check: original tenant rides the checkpoint metadata
    # (set via invoke config metadata in api/draft.py).
    original_tenant = (snapshot.metadata or {}).get("tenant_id")
    if original_tenant and original_tenant != tenant_id:
        raise TenantMismatch(body.run_id)

    if not snapshot.next:  # no pending node → terminal state
        raise RunNotPaused(body.run_id)

    capture = ToolCallCapture()
    result = agent.invoke(
        Command(resume=_decision_payload(body)),
        config={**cfg, "callbacks": [capture],
                "tags": ["m1", "draft-solicitation", "resume"],
                "metadata": {"request_id": request_id, "tenant_id": tenant_id}},
    )

    if result.get("__interrupt__"):
        # Rare: an edit decision produced ANOTHER hitl-band score.
        final = _interrupted_final(
            result["__interrupt__"], section_id=section_id,
            request_id=request_id, run_id=body.run_id,
        )
        return final, capture.records

    final: FinalDraftSection = result["structured_response"]
    final = final.model_copy(update={"request_id": request_id, "run_id": body.run_id})
    return final, capture.records


@router.post("/section/resume")
async def resume_section(
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
        body = ResumeSectionRequest.model_validate(raw_body)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=422,
            content={"error": "invalid_request", "details": str(exc),
                     "request_id": request_id},
        )

    if body.decision == "edit" and body.edited_args is None:
        return JSONResponse(
            status_code=422,
            content={"error": "edited_args_required", "request_id": request_id},
        )

    try:
        final, tool_calls = _resume_agent(
            body, tenant_id=x_tenant_id, request_id=request_id
        )
    except RunNotFound:
        return JSONResponse(
            status_code=404,
            content={"error": "run_not_found", "request_id": request_id},
        )
    except TenantMismatch:
        return JSONResponse(
            status_code=403,
            content={"error": "tenant_mismatch", "request_id": request_id},
        )
    except RunNotPaused:
        return JSONResponse(
            status_code=409,
            content={"error": "run_not_paused", "request_id": request_id},
        )
    except CitationVerificationFailed as exc:
        _audit_safe(
            action="agent_resume", tenant_id=x_tenant_id, request_id=request_id,
            outcome="citation_verification_failed", run_id=body.run_id,
            resume={"decision": body.decision,
                    "edited_args_hash": _sha256_or_none(body.edited_args),
                    "reason_hash": _sha256_or_none(body.reason)},
        )
        return JSONResponse(
            status_code=422,
            content={"error": "citation_verification_failed",
                     "unknown_chunk_ids": exc.unknown_ids,
                     "request_id": request_id},
        )
    except Exception as exc:  # noqa: BLE001
        log.error("resume failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"error": "bedrock_unavailable", "request_id": request_id},
        )

    # Audit: agent_resume row joining the original draft row on run_id (§11.1).
    _audit_safe(
        action="agent_resume",
        tenant_id=x_tenant_id,
        request_id=request_id,
        outcome=final.outcome,
        run_id=body.run_id,
        actor={"user_id": x_user_id, "role": None, "session_id": None},
        resume={
            "decision": body.decision,
            "edited_args_hash": _sha256_or_none(body.edited_args),
            "reason_hash": _sha256_or_none(body.reason),
        },
        generation={"model": config.BEDROCK_GEN_MODEL},
        tool_calls=tool_calls,
    )

    return JSONResponse(status_code=200, content=final.model_dump(mode="json"))
