"""``POST /draft-solicitation/batch`` — per-AI-Part batch drafting.

Design ref §18.2 + §18.12.2 (ADR-0014). Pipeline: rate-limit (multi-cost per
ADR-0013 D7.1 — a batch of N Parts costs N against the per-tenant budget) →
preflight_batch (ADR-0015) → coordinator graph → audit → bundle response.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app import audit as audit_mod
from app import config
from app.agents.schemas import (
    BatchDraftRequest,
    PendingToolCall,
    SolicitationDraftBundle,
)
from app.api.draft import _tenant_key, limiter
from app.api.preflight import preflight_batch

log = logging.getLogger("ai-orchestrator.batch")

router = APIRouter(prefix="/draft-solicitation", tags=["draft"])


def _audit_safe(**kwargs: object) -> None:
    try:
        audit_mod.write_audit_log(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover
        log.error("audit write failed: %s", exc)


def _planned_parts(body: BatchDraftRequest) -> list[str]:
    from app.agents.coordinator.nodes import AI_PART_TO_SECTIONS  # noqa: PLC0415

    return [
        part
        for part, sections in AI_PART_TO_SECTIONS.items()
        if any(body.provenances.get(s) is None for s in sections)  # type: ignore[arg-type]
    ]


def _charge_extra_cost(request: Request, n: int) -> None:
    """Multi-cost rate limit (ADR-0013 D7.1): the decorator consumed 1; charge
    n-1 more so a batch of n Parts costs n. Best-effort — storage backends
    without cost support fall back to a hit-per-unit loop."""
    if n <= 1:
        return
    try:
        from limits import parse_many  # noqa: PLC0415

        key = _tenant_key(request)
        strategy = limiter.limiter
        items = parse_many(
            f"{config.RATE_LIMIT_QUERIES_PER_MINUTE_PER_TENANT}/minute;"
            f"{config.RATE_LIMIT_QUERIES_PER_DAY_PER_TENANT}/day"
        )
        for item in items:
            try:
                strategy.hit(item, key, cost=n - 1)
            except TypeError:  # older limits — no cost kwarg
                for _ in range(n - 1):
                    strategy.hit(item, key)
    except Exception as exc:  # pragma: no cover — never block the draft on this
        log.warning("multi-cost charge failed (continuing): %s", exc)


def _initial_state(
    body: BatchDraftRequest, *, tenant_id: str, request_id: str, batch_run_id: str
) -> dict:
    return {
        "solicitation_id": body.solicitation_id,
        "tenant_id": tenant_id,
        "request_id": request_id,
        "batch_run_id": batch_run_id,
        "naics": body.naics,
        "set_aside": body.set_aside,
        "contract_type": body.contract_type,
        "agency_supplement": body.agency_supplement,
        "user_constraints_by_section": dict(body.user_constraints_by_section),
        "provenances": dict(body.provenances),
        "part_iii_attachments": list(body.part_iii_attachments),
        "part_results": [],
        "bundle": None,
        "skip_critic": False,
    }


def _coordinator_config(*, batch_run_id: str, tenant_id: str, request_id: str) -> dict:
    return {
        "configurable": {"thread_id": batch_run_id, "tenant_id": tenant_id},
        "tags": ["m1", "batch-coordinator"],
        "metadata": {
            "request_id": request_id,
            "batch_run_id": batch_run_id,
            "tenant_id": tenant_id,
        },
    }


def interrupted_bundle_from_state(
    result: dict, *, solicitation_id: str, request_id: str, batch_run_id: str
) -> SolicitationDraftBundle:
    """Synthesize the batch_interrupted bundle from a paused coordinator state.

    The parent paused inside one or more draft_part nodes, so ``aggregate``
    never ran — assemble what completed plus one PendingToolCall per parent
    interrupt (shared with /batch/resume's repeat-interrupt path).
    """
    parts = {r.part: r for r in result.get("part_results", [])}
    pending: list[PendingToolCall] = []
    for intr in result.get("__interrupt__", []):
        value = getattr(intr, "value", intr)
        if isinstance(value, dict) and "tool_name" in value:
            pending.append(PendingToolCall(**value))
    return SolicitationDraftBundle(
        solicitation_id=solicitation_id,
        parts=parts,  # type: ignore[arg-type]
        overall_outcome="batch_interrupted",
        consistency_report=None,
        pending_interrupts=pending,
        request_id=request_id,
        batch_run_id=batch_run_id,
    )


def _run_coordinator(
    body: BatchDraftRequest, *, tenant_id: str, request_id: str, batch_run_id: str
) -> SolicitationDraftBundle:
    """Invoke the coordinator graph; map paused state to an interrupted bundle.

    Tests monkeypatch this seam for handler-contract tests.
    """
    from app.agents.coordinator.graph import build_coordinator_graph  # noqa: PLC0415

    graph = build_coordinator_graph()
    result = graph.invoke(
        _initial_state(
            body, tenant_id=tenant_id, request_id=request_id, batch_run_id=batch_run_id
        ),
        config=_coordinator_config(
            batch_run_id=batch_run_id, tenant_id=tenant_id, request_id=request_id
        ),
    )
    if result.get("__interrupt__"):
        return interrupted_bundle_from_state(
            result, solicitation_id=body.solicitation_id,
            request_id=request_id, batch_run_id=batch_run_id,
        )
    bundle: SolicitationDraftBundle = result["bundle"]
    return bundle


@router.post("/batch")
@limiter.limit(
    f"{config.RATE_LIMIT_QUERIES_PER_MINUTE_PER_TENANT}/minute;"
    f"{config.RATE_LIMIT_QUERIES_PER_DAY_PER_TENANT}/day"
)
async def draft_batch(
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
        body = BatchDraftRequest.model_validate(raw_body)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=422,
            content={"error": "invalid_request", "details": str(exc),
                     "request_id": request_id},
        )

    # Preflight (ADR-0015 D2) — all Step 1 metadata hard-required for batch.
    preflight = preflight_batch(body, x_tenant_id)
    if not preflight.ready:
        _audit_safe(
            action="preflight_rejected", tenant_id=x_tenant_id,
            request_id=request_id, outcome="preflight_rejected",
            preflight=preflight.model_dump(),
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": "preflight_rejected_missing_required",
                "missing_required": preflight.missing_required,
                "request_id": request_id,
            },
        )

    planned = _planned_parts(body)
    _charge_extra_cost(request, len(planned))

    batch_run_id = f"{body.solicitation_id}:batch:{request_id}"

    try:
        bundle = _run_coordinator(
            body, tenant_id=x_tenant_id, request_id=request_id,
            batch_run_id=batch_run_id,
        )
    except Exception as exc:  # noqa: BLE001
        log.error("coordinator failure: %s", exc)
        _audit_safe(
            action="batch_coordinator_run", tenant_id=x_tenant_id,
            request_id=request_id, outcome="coordinator_failure",
            run_id=batch_run_id,
        )
        return JSONResponse(
            status_code=500,
            content={"error": "coordinator_failure", "request_id": request_id},
        )

    # Audit row (design ref §18.7, part-level §18.12.2 shape).
    sections_status: dict[str, list[str]] = {
        "drafted": [], "interrupted": [], "withheld": [],
    }
    for part_result in bundle.parts.values():
        for sid, final in part_result.sections.items():
            outcome = getattr(final, "outcome", None)
            if outcome == "draft_returned":
                sections_status["drafted"].append(sid)
            elif outcome == "interrupted":
                sections_status["interrupted"].append(sid)
            elif outcome == "withheld":
                sections_status["withheld"].append(sid)
    _audit_safe(
        action="batch_coordinator_run",
        tenant_id=x_tenant_id,
        request_id=request_id,
        outcome=bundle.overall_outcome,
        run_id=batch_run_id,
        actor={"user_id": x_user_id, "role": None, "session_id": None},
        preflight=preflight.model_dump(),
        batch={
            "parts_planned": planned,
            "sections_drafted": sorted(sections_status["drafted"]),
            "sections_interrupted": sorted(sections_status["interrupted"]),
            "sections_withheld": sorted(sections_status["withheld"]),
            "rate_limit_cost": len(planned),
        },
    )

    return JSONResponse(status_code=200, content=bundle.model_dump(mode="json"))
