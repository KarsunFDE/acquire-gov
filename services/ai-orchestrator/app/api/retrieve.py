"""``POST /retrieve`` router — M2 grounded retrieval endpoint.

Endpoint contract: ``docs/specs/m2-grounded-retrieval/retrieval-pipeline.md`` §4.1.
Pipeline: spec §3 stages 1-8, 12. ADRs ADR-0006, ADR-0007, ADR-0008,
ADR-0011 D2/D4.

Pipeline-owned modules (``app.guardrails``, ``app.retrieval``, ``app.rerank``,
``app.audit``) are imported at module load; tests inject fakes by
``monkeypatch.setattr`` on this module's references. slowapi rate-limit
runs per ``X-Tenant-ID`` (ADR-0011 D4 — 30/min, 1000/day per tenant).
"""
from __future__ import annotations

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from app import audit as audit_mod
from app import config
from app.guardrails import QueryGuardrails
from app.retrieval import build_far_retriever, classify_query
from app.rerank import rerank_and_gate

log = logging.getLogger("ai-orchestrator.retrieve")

router = APIRouter(tags=["retrieve"])


# Per-tenant key extractor — spec §3 stage 1 and ADR-0011 D4.
def _tenant_key(request: Request) -> str:
    return request.headers.get("X-Tenant-ID") or get_remote_address(request)


# In-process limiter (Phase 1.5 swaps to Redis per ADR-0011 D4 / spec §14).
limiter = Limiter(key_func=_tenant_key)


_FAR_SECTION_ENUM: set[str] = {
    "A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M",
}


class RetrieveRequest(BaseModel):
    """``POST /retrieve`` body — spec §4.1.

    ``k`` is hard-capped at 20 (>20 → 422 ``k_exceeded``); ``query`` is
    Pydantic-bounded at 2000 chars (spec §10 ``MAX_QUERY_CHARS``).
    """

    query: str = Field(min_length=1, max_length=config.MAX_QUERY_CHARS)
    far_section_filter: list[str] | None = Field(default=None, max_length=12)
    k: int | None = Field(default=None)

    @field_validator("far_section_filter")
    @classmethod
    def _check_sections(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        bad = [s for s in v if s not in _FAR_SECTION_ENUM]
        if bad:
            raise ValueError(f"unknown far_section values: {bad}")
        return v


def _normalize_chunk(c: dict) -> dict:
    """Map an internal retrieval/rerank chunk to the response shape per
    spec §4.1 citations[] entry."""
    return {
        "chunk_id": str(c.get("chunk_id") or c.get("_id") or ""),
        "text": c.get("text", ""),
        "far_part": c.get("far_part", ""),
        "far_section": c.get("far_section", ""),
        "far_subsection": c.get("far_subsection"),
        "far_clause": c.get("far_clause"),
        "source_doc": c.get("source_doc", ""),
        "snapshot_date": str(c.get("snapshot_date", "")),
        "relevance_score": c.get("relevance_score", 0.0),
    }


def _audit_safe(**kwargs: object) -> None:
    """Best-effort audit write — synchronous on the path but never
    propagates an exception to the client past the 503 mapping a caller
    might already be doing. ``audit.write_audit_log`` is sync (ADR-0008 D3
    write-through); if it raises, we log and continue so the response
    still gets out. Spec §9 says Mongo write failure → 503; the file
    fallback in ``app.audit`` handles dev. Tests assert on the captured
    rows."""
    try:
        audit_mod.write_audit_log(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover — audit fallback covers this
        log.error("audit write failed: %s", exc)


@router.post("/retrieve")
@limiter.limit(
    f"{config.RATE_LIMIT_QUERIES_PER_MINUTE_PER_TENANT}/minute;"
    f"{config.RATE_LIMIT_QUERIES_PER_DAY_PER_TENANT}/day"
)
async def retrieve(
    request: Request,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> JSONResponse:
    """Spec §4.1 — query guardrail + hybrid retrieval + rerank gate."""
    request_id = x_request_id or str(uuid.uuid4())

    if not x_tenant_id:
        return JSONResponse(
            status_code=400,
            content={"error": "tenant_id_required", "request_id": request_id},
        )

    raw_body = await request.json()

    # Pre-pydantic k cap (spec §4.1 — k > 20 → 422 k_exceeded).
    if isinstance(raw_body, dict):
        k_val = raw_body.get("k")
        if isinstance(k_val, int) and k_val > config.RETRIEVAL_K_CANDIDATES:
            return JSONResponse(
                status_code=422,
                content={
                    "error": "k_exceeded",
                    "max": config.RETRIEVAL_K_CANDIDATES,
                    "request_id": request_id,
                },
            )

    try:
        body = RetrieveRequest.model_validate(raw_body)
    except Exception as exc:  # noqa: BLE001 — pydantic ValidationError
        return JSONResponse(
            status_code=422,
            content={
                "error": "invalid_request",
                "details": str(exc),
                "request_id": request_id,
            },
        )

    # Spec §3 stage 2 — query guardrail.
    guardrail = QueryGuardrails()
    decision = guardrail.evaluate(body.query, tenant_id=x_tenant_id, request_id=request_id)
    if decision.action == "reject":
        # Guardrails wrote its own query_blocked audit row already.
        return JSONResponse(
            status_code=403,
            content={
                "error": "query_blocked",
                "reason": decision.reason,
                "request_id": request_id,
            },
        )

    # Spec §3 stages 3-7 — retrieve + rerank + gate.
    vector_w, fulltext_w = classify_query(body.query)
    try:
        retriever = build_far_retriever(
            tenant_id=x_tenant_id,
            vector_weight=vector_w,
            fulltext_weight=fulltext_w,
        )
        candidates = list(retriever.invoke(body.query))
    except Exception as exc:
        log.error("retrieval failed: %s", exc)
        _audit_safe(
            action="retrieval_only",
            tenant_id=x_tenant_id,
            request_id=request_id,
            outcome="retrieval_failed",
            query=body.query,
        )
        return JSONResponse(
            status_code=503,
            content={"error": "mongo_unavailable", "request_id": request_id},
        )

    try:
        gate_decision, top = rerank_and_gate(body.query, candidates)
    except Exception as exc:
        # Spec §9 — rerank exhaustion → 200 + rerank_unavailable_passthrough.
        log.warning("rerank failed: %s; passthrough", exc)
        top = candidates[: config.RERANK_TOP_N]
        gate_decision = "pass"  # downgraded below into passthrough branch
        _audit_safe(
            action="retrieval_only",
            tenant_id=x_tenant_id,
            request_id=request_id,
            outcome="rerank_unavailable_hitl",
            query=body.query,
            retrieval={
                "vector_weight": vector_w,
                "fulltext_weight": fulltext_w,
                "gate_decision": "rerank_unavailable_passthrough",
            },
        )
        return JSONResponse(
            status_code=200,
            content={
                "outcome": "retrieved",
                "gate_decision": "rerank_unavailable_passthrough",
                "rerank_top_score": None,
                "requires_human_review": True,
                "citations": [
                    {k: v for k, v in _normalize_chunk(c).items()
                     if k != "relevance_score"}
                    for c in top
                ],
                "request_id": request_id,
            },
        )

    top_score = top[0].get("relevance_score", 0.0) if top else 0.0
    citations = [_normalize_chunk(c) for c in top]

    if gate_decision == "withhold":
        _audit_safe(
            action="retrieval_only",
            tenant_id=x_tenant_id,
            request_id=request_id,
            outcome="withheld",
            query=body.query,
            retrieval={
                "vector_weight": vector_w,
                "fulltext_weight": fulltext_w,
                "gate_decision": "withhold",
            },
        )
        return JSONResponse(
            status_code=200,
            content={
                "outcome": "withheld",
                "reason": "insufficient_grounding",
                "gate_decision": "withhold",
                "rerank_top_score": top_score,
                "citations": [],
                "request_id": request_id,
            },
        )

    outcome = "retrieved"
    requires_review = gate_decision == "hitl"
    audit_outcome = "hitl_pending" if requires_review else "retrieved"
    _audit_safe(
        action="retrieval_only",
        tenant_id=x_tenant_id,
        request_id=request_id,
        outcome=audit_outcome,
        query=body.query,
        retrieval={
            "vector_weight": vector_w,
            "fulltext_weight": fulltext_w,
            "gate_decision": gate_decision,
            "rerank_top_score": top_score,
        },
    )
    payload: dict[str, object] = {
        "outcome": outcome,
        "gate_decision": gate_decision,
        "rerank_top_score": top_score,
        "citations": citations,
        "request_id": request_id,
    }
    if requires_review:
        payload["requires_human_review"] = True
    return JSONResponse(status_code=200, content=payload)
