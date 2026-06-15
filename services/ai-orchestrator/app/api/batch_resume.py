"""``POST /draft-solicitation/batch/resume`` — resume a paused batch run.

Design ref §18.2. The handler reads the coordinator checkpoint, maps each
``BatchPerSectionDecision`` to its owning Part's parent interrupt (decisions
stay keyed by section_id for client compat — ADR-0014 §18.12.3 note), builds
the per-interrupt ``Command(resume={...})`` payload, and resumes the parent
graph. Children that completed in the original batch are preserved in state —
no re-drafting, no re-spend. No preflight: the checkpointed state already
passed it on the original ``/batch`` call.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app import audit as audit_mod
from app.agents.schemas import (
    BatchPerSectionDecision,
    BatchResumeRequest,
    SolicitationDraftBundle,
)

log = logging.getLogger("ai-orchestrator.batch-resume")

router = APIRouter(prefix="/draft-solicitation", tags=["draft"])


class BatchRunNotFound(Exception):
    pass


class BatchRunNotPaused(Exception):
    pass


class TenantMismatch(Exception):
    pass


class DecisionCountMismatch(Exception):
    pass


def _audit_safe(**kwargs: object) -> None:
    try:
        audit_mod.write_audit_log(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover
        log.error("audit write failed: %s", exc)


def _hitl_response(decision: BatchPerSectionDecision) -> dict:
    """BatchPerSectionDecision → the child's HITLResponse payload."""
    if decision.decision == "approve":
        return {"decisions": [{"type": "approve"}]}
    if decision.decision == "edit":
        return {
            "decisions": [{
                "type": "edit",
                "edited_action": {
                    "name": "compute_gate_decision",
                    "args": decision.edited_args or {},
                },
            }]
        }
    return {
        "decisions": [{
            "type": "reject",
            "message": decision.reason or "CO rejected the gate decision",
        }]
    }


def _resume_coordinator(
    body: BatchResumeRequest, *, tenant_id: str, request_id: str
) -> SolicitationDraftBundle:
    """Map decisions to parent interrupts and resume. Tests monkeypatch this."""
    from langgraph.types import Command  # noqa: PLC0415

    from app.agents.coordinator.graph import build_coordinator_graph  # noqa: PLC0415
    from app.api.batch import interrupted_bundle_from_state  # noqa: PLC0415

    graph = build_coordinator_graph()
    cfg = {"configurable": {"thread_id": body.batch_run_id, "tenant_id": tenant_id},
           "metadata": {"request_id": request_id, "tenant_id": tenant_id}}

    snapshot = graph.get_state(cfg)
    if snapshot is None or not snapshot.config.get("configurable", {}).get("checkpoint_id"):
        raise BatchRunNotFound(body.batch_run_id)

    original_tenant = (snapshot.metadata or {}).get("tenant_id")
    if original_tenant and original_tenant != tenant_id:
        raise TenantMismatch(body.batch_run_id)

    interrupts = [i for task in snapshot.tasks for i in (task.interrupts or [])]
    if not snapshot.next or not interrupts:
        raise BatchRunNotPaused(body.batch_run_id)

    # Map decisions (keyed by section) onto the owning Part's interrupt.
    decision_by_section = {d.section_id: d for d in body.decisions}
    resume_map: dict[str, dict] = {}
    matched_sections: set[str] = set()
    for intr in interrupts:
        value = getattr(intr, "value", {}) or {}
        part_sections = (value.get("args") or {}).get("sections") or []
        chosen = next(
            (decision_by_section[s] for s in part_sections if s in decision_by_section),
            None,
        )
        if chosen is None:
            raise DecisionCountMismatch(
                f"no decision provided for interrupted Part sections {part_sections}"
            )
        matched_sections.update(s for s in part_sections if s in decision_by_section)
        resume_map[intr.id] = _hitl_response(chosen)

    unmatched = set(decision_by_section) - matched_sections
    if unmatched:
        raise DecisionCountMismatch(f"decisions for non-interrupted sections: {sorted(unmatched)}")

    resume_value: object = (
        next(iter(resume_map.values())) if len(resume_map) == 1 else resume_map
    )
    result = graph.invoke(Command(resume=resume_value), config=cfg)

    if result.get("__interrupt__"):
        sol_id, _, req = body.batch_run_id.partition(":batch:")
        return interrupted_bundle_from_state(
            result, solicitation_id=sol_id, request_id=req,
            batch_run_id=body.batch_run_id,
        )
    bundle: SolicitationDraftBundle = result["bundle"]
    return bundle


@router.post("/batch/resume")
async def resume_batch(
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
        body = BatchResumeRequest.model_validate(raw_body)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=422,
            content={"error": "invalid_request", "details": str(exc),
                     "request_id": request_id},
        )

    for d in body.decisions:
        if d.decision == "edit" and d.edited_args is None:
            return JSONResponse(
                status_code=422,
                content={"error": "edited_args_required", "request_id": request_id},
            )

    try:
        bundle = _resume_coordinator(body, tenant_id=x_tenant_id, request_id=request_id)
    except BatchRunNotFound:
        return JSONResponse(
            status_code=404,
            content={"error": "batch_run_not_found", "request_id": request_id},
        )
    except TenantMismatch:
        return JSONResponse(
            status_code=403,
            content={"error": "tenant_mismatch", "request_id": request_id},
        )
    except BatchRunNotPaused:
        return JSONResponse(
            status_code=409,
            content={"error": "batch_run_not_paused", "request_id": request_id},
        )
    except DecisionCountMismatch:
        return JSONResponse(
            status_code=422,
            content={"error": "decision_count_mismatch", "request_id": request_id},
        )
    except Exception as exc:  # noqa: BLE001
        log.error("batch resume failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "coordinator_failure", "request_id": request_id},
        )

    _audit_safe(
        action="batch_resume",
        tenant_id=x_tenant_id,
        request_id=request_id,
        outcome=bundle.overall_outcome,
        run_id=body.batch_run_id,
        actor={"user_id": x_user_id, "role": None, "session_id": None},
        resume={
            "decisions": [
                {"section_id": d.section_id, "decision": d.decision}
                for d in body.decisions
            ]
        },
    )

    return JSONResponse(status_code=200, content=bundle.model_dump(mode="json"))
