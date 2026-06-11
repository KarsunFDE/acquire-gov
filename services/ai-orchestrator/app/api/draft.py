"""``POST /draft-solicitation/section`` router — M1 agentic grounded drafting.

Rewritten around ``create_agent`` per ADR-0012 (design ref §2–§9, §19.3):

    rate-limit → guardrails → preflight → build agent → agent.invoke →
    audit row (tool_calls[] sub-record) → FinalDraftSection response

The handler does NOT call retrieval or rerank directly — those happen inside
tool calls the agent makes. The handler's job is: construct the agent, invoke
it, format the response, write the audit row.

Stub fallback (CLAUDE.md D-060): when no Bedrock credentials are present the
handler runs retrieval + rerank + gate programmatically and returns a
deterministic stub draft, so first-day dev laptops still get an end-to-end
flow without AWS spend.

This router is separate from the brownfield-debt ``/draft-solicitation``
endpoint in ``app/main.py`` (Item 4) — both intentionally coexist; see
CLAUDE.md "brownfield-debt invariant".
"""
from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app import audit as audit_mod
from app import config
from app.agents.checkpointer import thread_id_for
from app.agents.schemas import (
    Citation,
    DraftSectionRequest,
    FinalDraftSection,
    PreflightResult,
)
from app.api.preflight import preflight_single_section
from app.citations import CitationVerificationFailed
from app.guardrails import QueryGuardrails

log = logging.getLogger("ai-orchestrator.draft")

router = APIRouter(prefix="/draft-solicitation", tags=["draft"])


def _tenant_key(request: Request) -> str:
    return request.headers.get("X-Tenant-ID") or get_remote_address(request)


limiter = Limiter(key_func=_tenant_key)


def _default_query(section_id: str) -> str:
    """Section-specific template default (M2 spec §4.2, unchanged)."""
    return (
        f"Draft FAR Section {section_id} content using the retrieved "
        f"FAR/DFARS context. Cite chunk_ids for every authoritative claim."
    )


def _bedrock_creds_present() -> bool:
    return bool(
        os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
        or os.environ.get("AWS_ACCESS_KEY_ID")
    )


def _audit_safe(**kwargs: object) -> None:
    try:
        audit_mod.write_audit_log(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover
        log.error("audit write failed: %s", exc)


# ---------------------------------------------------------------------------
# Agent invocation (monkeypatched by tests)
# ---------------------------------------------------------------------------


def _agent_user_message(body: DraftSectionRequest, query: str) -> str:
    return (
        f"Draft FAR UCF Section {body.section_id} for solicitation "
        f"{body.solicitation_id}.\n"
        f"naics: {body.naics or '(unset)'}\n"
        f"set_aside: {body.set_aside or '(unset)'}\n"
        f"contract_type: {body.contract_type or '(unset)'}\n"
        f"agency_supplement: {body.agency_supplement or '(unset)'}\n"
        f"user_constraints: {body.constraints or '(none)'}\n"
        f"request: {query}"
    )


def _invoke_config(
    *, run_id: str, tenant_id: str, co_user_id: str | None,
    request_id: str, solicitation_id: str, section_id: str, callbacks: list,
) -> dict:
    """RunnableConfig per design ref §9.2 — thread_id keys the checkpoint;
    tags/metadata are LangSmith-searchable filters."""
    return {
        "configurable": {
            "thread_id": run_id,
            "tenant_id": tenant_id,
            "co_user_id": co_user_id,
        },
        "callbacks": callbacks,
        "tags": ["m1", "draft-solicitation", f"section-{section_id}"],
        "metadata": {
            "request_id": request_id,
            "solicitation_id": solicitation_id,
            "section_id": section_id,
            "tenant_id": tenant_id,
        },
    }


def _run_agent(
    body: DraftSectionRequest,
    query: str,
    *,
    tenant_id: str,
    request_id: str,
    run_id: str,
    co_user_id: str | None = None,
) -> tuple[FinalDraftSection, list]:
    """Build + invoke the section-drafter agent; return (final, tool_calls).

    Falls back to :func:`_stub_run` when no Bedrock credentials are present
    (CLAUDE.md D-060 first-day-learner path). Tests monkeypatch this function
    for deterministic handler tests, or monkeypatch deeper (builder._harness_chat)
    for agent-loop tests.
    """
    if not _bedrock_creds_present():
        return _stub_run(body, query, tenant_id=tenant_id, request_id=request_id, run_id=run_id)

    from app.agents.builder import build_section_drafter_agent  # noqa: PLC0415
    from app.agents.tool_call_capture import ToolCallCapture  # noqa: PLC0415

    capture = ToolCallCapture()
    agent = build_section_drafter_agent()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": _agent_user_message(body, query)}]},
        config=_invoke_config(
            run_id=run_id, tenant_id=tenant_id, co_user_id=co_user_id,
            request_id=request_id, solicitation_id=body.solicitation_id,
            section_id=body.section_id, callbacks=[capture],
        ),
    )
    final: FinalDraftSection = result["structured_response"]
    # Authoritative identifiers come from the handler, not the model.
    final = final.model_copy(update={"request_id": request_id, "run_id": run_id})
    return final, capture.records


def _stub_run(
    body: DraftSectionRequest,
    query: str,
    *,
    tenant_id: str,
    request_id: str,
    run_id: str,
) -> tuple[FinalDraftSection, list]:
    """Credential-free deterministic path: real retrieval + rerank + gate,
    stubbed generation (mirrors the M2 ``_invoke_chat`` stub contract)."""
    from app import rerank, retrieval  # noqa: PLC0415
    from app.agents.tools.gate import compute_gate_decision  # noqa: PLC0415
    from app.agents.tools.retrieve_far import _to_chunk  # noqa: PLC0415

    vector_w, fulltext_w = retrieval.classify_query(query)
    retriever = retrieval.build_far_retriever(
        tenant_id=tenant_id, vector_weight=vector_w, fulltext_weight=fulltext_w
    )
    candidates = list(retriever.invoke(query))
    reranked = rerank.rerank_only(query, candidates)
    gate = compute_gate_decision.func(rerank_top_score=reranked.top_score)  # type: ignore[attr-defined]

    if gate.gate_decision == "withhold":
        final = FinalDraftSection(
            outcome="withheld",
            section_text=None,
            section_id=body.section_id,
            citations=[],
            gate_decision="withhold",
            requires_human_review=True,
            rerank_top_score=reranked.top_score,
            request_id=request_id,
            run_id=run_id,
        )
        return final, []

    chunks = [_to_chunk(c) for c in reranked.top]
    citations = [
        Citation(
            chunk_id=c.chunk_id,
            far_part=c.far_part,
            far_section=c.far_section,
            far_clause=c.far_clause,
            snapshot_date=c.snapshot_date,
            relevance_score=c.relevance_score,
            text=c.text,
        )
        for c in chunks
    ]
    final = FinalDraftSection(
        outcome="draft_returned",
        section_text=(
            f"[stub draft — no Bedrock credentials] Section {body.section_id} "
            f"grounded on {len(citations)} retrieved chunk(s)."
        ),
        section_id=body.section_id,
        citations=citations,
        gate_decision=gate.gate_decision,
        requires_human_review=gate.gate_decision != "pass",
        rerank_top_score=reranked.top_score,
        request_id=request_id,
        run_id=run_id,
    )
    return final, []


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/section")
@limiter.limit(
    f"{config.RATE_LIMIT_QUERIES_PER_MINUTE_PER_TENANT}/minute;"
    f"{config.RATE_LIMIT_QUERIES_PER_DAY_PER_TENANT}/day"
)
async def draft_section(
    request: Request,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> JSONResponse:
    """Design ref §4.1 + §19.3 — guardrails → preflight → agent → audit."""
    request_id = x_request_id or str(uuid.uuid4())

    if not x_tenant_id:
        return JSONResponse(
            status_code=400,
            content={"error": "tenant_id_required", "request_id": request_id},
        )

    raw_body = await request.json()
    try:
        body = DraftSectionRequest.model_validate(raw_body)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=422,
            content={
                "error": "invalid_request",
                "details": str(exc),
                "request_id": request_id,
            },
        )

    query = body.query or _default_query(body.section_id)

    # 1. Guardrails (ADR-0011 D2).
    guardrail = QueryGuardrails()
    decision = guardrail.evaluate(query, tenant_id=x_tenant_id, request_id=request_id)
    if decision.action == "reject":
        return JSONResponse(
            status_code=403,
            content={
                "error": "query_blocked",
                "reason": decision.reason,
                "request_id": request_id,
            },
        )

    # 2. Preflight (ADR-0015 D2) — hard-missing → 422 before any agent spend.
    preflight: PreflightResult = preflight_single_section(body, x_tenant_id)
    if not preflight.ready:
        _audit_safe(
            action="preflight_rejected",
            tenant_id=x_tenant_id,
            request_id=request_id,
            outcome="preflight_rejected",
            query=query,
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

    run_id = thread_id_for(
        solicitation_id=body.solicitation_id,
        section_id=body.section_id,
        request_id=request_id,
    )

    # 3. Agent run.
    try:
        final, tool_calls = _run_agent(
            body, query,
            tenant_id=x_tenant_id, request_id=request_id,
            run_id=run_id, co_user_id=x_user_id,
        )
    except CitationVerificationFailed as exc:
        _audit_safe(
            action="retrieval_and_generate",
            tenant_id=x_tenant_id,
            request_id=request_id,
            outcome="citation_verification_failed",
            query=query,
            preflight=preflight.model_dump(),
            retrieval={"unknown_chunk_ids": exc.unknown_ids},
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": "citation_verification_failed",
                "unknown_chunk_ids": exc.unknown_ids,
                "request_id": request_id,
            },
        )
    except ValueError as exc:
        if "draft_parse_failed" in str(exc):
            _audit_safe(
                action="retrieval_and_generate",
                tenant_id=x_tenant_id,
                request_id=request_id,
                outcome="draft_parse_failed",
                query=query,
                preflight=preflight.model_dump(),
            )
            return JSONResponse(
                status_code=422,
                content={"error": "draft_parse_failed", "request_id": request_id},
            )
        raise
    except Exception as exc:  # noqa: BLE001 — outage classification below
        kind = _classify_outage(exc)
        log.error("agent run failed (%s): %s", kind, exc)
        _audit_safe(
            action="retrieval_and_generate",
            tenant_id=x_tenant_id,
            request_id=request_id,
            outcome="retrieval_failed" if kind == "mongo_unavailable" else "generation_failed",
            query=query,
            preflight=preflight.model_dump(),
        )
        return JSONResponse(
            status_code=503,
            content={"error": kind, "request_id": request_id},
        )

    # 4. Soft-degraded flags ride the response (ADR-0015 D5).
    final = final.model_copy(update={"degraded_context": preflight.degraded_context})

    # 5. Audit success row with tool_calls[] sub-record (ADR-0012 D9).
    _audit_safe(
        action="retrieval_and_generate",
        tenant_id=x_tenant_id,
        request_id=request_id,
        outcome=final.outcome,
        query=query,
        actor={"user_id": x_user_id, "role": None, "session_id": None},
        preflight=preflight.model_dump(),
        retrieval={
            "gate_decision": final.gate_decision,
            "rerank_top_score": final.rerank_top_score,
        },
        generation={"model": config.BEDROCK_GEN_MODEL},
        tool_calls=tool_calls,
        run_id=run_id,
    )

    return JSONResponse(status_code=200, content=final.model_dump(mode="json"))


def _classify_outage(exc: Exception) -> str:
    """Map infrastructure failures to the §4.1 status-table error keys."""
    names = {type(exc).__name__} | {
        base.__name__ for base in type(exc).__mro__
    }
    if names & {"PyMongoError", "ServerSelectionTimeoutError", "ConnectionFailure"}:
        return "mongo_unavailable"
    return "bedrock_unavailable"
