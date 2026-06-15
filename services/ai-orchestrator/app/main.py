"""
ai-orchestrator — main FastAPI entrypoint.

DELIBERATE BROWNFIELD DEBT (annotated for cohort discovery):

  Item 4 — No structured-output validation. /draft-solicitation returns the
           raw stub response (sometimes {"clause_id": null, ...}); downstream
           Spring service hits NullPointerException on .clause_id.toString().
           Newer endpoints (/draft-amendment, /answer-qa, /eval/ssdd-draft,
           /eval/factor-suggest, /agent/intake-triage) ALSO return raw dict —
           same Pydantic-validation drift across 4 distinct AI endpoints.

  Item 6 (partial) — No correlation-ID logging at all. Other services log
           X-Request-ID / correlationId / traceId — this one logs nothing.

  Item 7 — pinecone-client is in requirements.txt but no `import pinecone`
           anywhere. Cohort removes in W2.

  Item 11 — Dockerfile uses :latest (the OTHER 4 services do; this one is
           hand-pinned to 3.11-slim per the comment block at the top of the
           ai-orchestrator Dockerfile).

  Plus: no retry, no streaming, no real Bedrock retry/cost accounting in
  this code path. Bedrock InvokeModel is wired (D-060 — real-Bedrock-from-W2
  authorized) via app/bedrock_client.py; if AWS creds aren't present, the
  client falls back to a stub.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.bedrock_client import invoke_model, BEDROCK_MODEL_ID, AWS_REGION

# M2 routers (additive — brownfield endpoints below remain per CLAUDE.md
# "brownfield-debt invariant"). Routers own their own slowapi limiters;
# we register the per-router limiter on app.state so SlowAPIMiddleware
# enforces it.
from app.api.draft import router as draft_router, limiter as draft_limiter
from app.api.ingest import router as ingest_router
from app.api.retrieve import router as retrieve_router, limiter as retrieve_limiter

# M1 agentic routers (ADR-0012 D8) + orphan-thread sweeper (D8.2).
from app.api.abandon import router as abandon_router
from app.api.resume import router as resume_router
from app.sweeper import sweep_orphan_threads

# M1 batch coordinator + critic routers (ADR-0013/0014).
from app.api.batch import router as batch_router
from app.api.batch_resume import router as batch_resume_router
from app.api.critic import router as critic_router

# ⚠ DELIBERATE — no correlation-ID in the log format (Item 6).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s - %(message)s",
)
log = logging.getLogger("ai-orchestrator")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Start the orphan-thread sweeper (ADR-0012 D8.2). Sweeper failures
    are contained inside the task — never the request path."""
    sweeper_task = asyncio.create_task(sweep_orphan_threads())
    try:
        yield
    finally:
        sweeper_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sweeper_task


app = FastAPI(title="ai-orchestrator", version="0.1.0-brownfield", lifespan=_lifespan)

# ---- M2 router wiring (ADR-0011 D4 — slowapi per-tenant rate limit) ----
# Use the retrieve-router limiter as the canonical app.state.limiter; the
# draft router shares the same Limiter contract (same key_func + caps).
app.state.limiter = retrieve_limiter


def _rate_limit_handler(_request, exc: RateLimitExceeded):  # type: ignore[no-untyped-def]
    from fastapi.responses import JSONResponse  # noqa: PLC0415
    return JSONResponse(
        status_code=429,
        content={"error": "rate_limited", "detail": str(exc.detail)},
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS — defense-in-depth. Browser traffic normally flows SPA -> gateway ->
# orchestrator (the gateway answers CORS), but allowing it here too covers
# direct-to-orchestrator dev calls and the generated pair-projects. Permissive
# dev posture: any origin, no credentials (callers send X-Tenant-ID headers,
# not cookies). Tighten allow_origins for any non-dev deployment.
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402,PLC0415

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
    max_age=3600,
)

app.include_router(retrieve_router)
app.include_router(draft_router)
app.include_router(ingest_router)
app.include_router(resume_router)
app.include_router(abandon_router)
app.include_router(batch_router)
app.include_router(batch_resume_router)
app.include_router(critic_router)


class DraftRequest(BaseModel):
    """
    ⚠ DELIBERATE — Item 4 reinforcement:
      No Field constraints, no examples, no descriptions. Cohort tightens
      in W1 Fri output validation.
    """
    topic: str
    constraints: str | None = None


class QaDraftRequest(BaseModel):
    """Vendor Q&A drafting request. ⚠ Item 4 — no Field constraints."""
    question: str
    solicitation_id: str | None = None
    constraints: str | None = None


class ClauseSearchRequest(BaseModel):
    """Hybrid RAG over FAR/DFARS clause library. ⚠ Item 4 — no Field."""
    query: str
    far_part: str | None = None
    agency_id: str | None = None  # ⚠ Item 10 surface — not enforced upstream
    top_k: int = 5


class FactorSuggestRequest(BaseModel):
    """Section M factor-narrative suggestion. ⚠ Item 4 — no Field."""
    topic: str
    constraints: str | None = None


class IntakeTriageRequest(BaseModel):
    """Multi-agent proposal-intake triage request. ⚠ Item 4 — no Field."""
    proposal_id: str
    solicitation_id: str | None = None
    raw_text: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    """
    ⚠ DELIBERATE: always returns 200. No DB ping, no Bedrock ping.
    Cohort adds real health check in W5 Tue OTel work.
    """
    return {"status": "ok", "service": "ai-orchestrator"}


@app.post("/draft-solicitation")
def draft_solicitation(req: DraftRequest) -> dict[str, Any]:
    """
    Section C SOW + Section L instructions drafting (Workflow 1).

    Bedrock invocation via app.bedrock_client.invoke_model (D-060 — real
    Bedrock from W2, falls back to stub if no AWS creds). Result is
    interleaved with the same 1-in-3 null-clause_id drift the locked test
    asserts (Item 4).

    ⚠ DELIBERATE GAPS (Item 4):
      - No Pydantic response model — returns raw dict.
      - 1-in-3 calls return {"clause_id": null, ...} to exercise the
        downstream NullPointerException path.
      - No retry, no streaming, no cost tracking, no structured-output
        schema enforced.
    """
    log.info("draft-solicitation called topic=%r constraints=%r",
             req.topic, req.constraints)

    # Bedrock call (D-060). Drops result into 'draft' field; preserves the
    # null-clause_id drift surface on top.
    bedrock = invoke_model(
        f"Draft a federal acquisition clause paragraph about: {req.topic}. "
        f"Constraints: {req.constraints or 'none'}.",
        system="You draft FAR/DFARS-compliant solicitation language.",
    )

    # ⚠ Item 4 — 1-in-3 returns null clause_id; downstream service can break.
    if random.randint(1, 3) == 1:
        return {
            "clause_id": None,  # ← will trigger downstream NPE
            "draft": bedrock["body"],
            "model": BEDROCK_MODEL_ID,
        }

    # Otherwise return a "happy" stub.
    return {
        "clause_id": f"FAR-52.{random.randint(200, 250)}-{random.randint(1, 30)}",
        "draft": bedrock["body"],
        "model": BEDROCK_MODEL_ID,
        "region": AWS_REGION,
    }


@app.post("/draft-amendment")
def draft_amendment(req: DraftRequest) -> dict[str, Any]:
    """
    Amendment narrative drafting (Workflow 2; FAR 15.206).

    ⚠ Item 4 — no Pydantic response model.
    ⚠ Item 6 — no correlation-id forwarded.
    """
    log.info("draft-amendment called topic=%r", req.topic)
    bedrock = invoke_model(
        f"Draft an amendment narrative for: {req.topic}. "
        f"Vendor-impact considerations: {req.constraints or 'standard scope change'}.",
        system="You draft FAR 15.206-compliant amendment narratives.",
    )
    return {
        "amendment_text": bedrock["body"],
        "model": BEDROCK_MODEL_ID,
        "predicted_vendor_impact": "re-acknowledgement required",
    }


@app.post("/answer-qa")
def answer_qa(req: QaDraftRequest) -> dict[str, Any]:
    """
    Vendor Q&A response drafting using clause-library RAG.

    ⚠ Item 4 — no Pydantic response model.
    ⚠ Item 6 — no correlation-id forwarded.
    ⚠ Item 9 reinforcement — req.question may contain raw HTML; we feed it
       directly into the prompt (prompt-injection-via-stored-content
       surface for W4 Wed OWASP LLM01).
    """
    log.info("answer-qa called question=%r", req.question[:60])
    bedrock = invoke_model(
        f"Vendor question: {req.question}\n\n"
        f"Draft a FAR-compliant agency answer. Cite clause IDs where applicable.",
        system="You answer vendor questions about federal solicitations.",
    )
    return {
        "answer_draft": bedrock["body"],
        "cited_clauses": [],  # ⚠ Item 4 — schema mismatch; sometimes the body
                              # contains clause refs but this list stays empty
        "model": BEDROCK_MODEL_ID,
    }


@app.post("/rag/clause-search")
def rag_clause_search(req: ClauseSearchRequest) -> dict[str, Any]:
    """
    Hybrid RAG over FAR/DFARS clause library (Atlas Vector Search).

    Cohort wires the Atlas hybrid retrieval in W2 (replacing the lexical-only
    stub here). Pinecone is listed in requirements.txt as "available vector
    store" but never imported (Item 7).

    ⚠ Item 6 — no correlation-id forwarded.
    ⚠ Item 7 — pinecone-client is in requirements.txt; this module does not
       import pinecone (stays unimported).
    """
    log.info("rag/clause-search query=%r far_part=%r top_k=%d",
             req.query[:60], req.far_part, req.top_k)
    # ⚠ Atlas Vector Search call would land here; stub returns a shaped
    # response so the surface flows.
    bedrock = invoke_model(
        f"Summarize FAR/DFARS clauses relevant to: {req.query}",
        system="You retrieve FAR/DFARS clauses; cite clause IDs.",
    )
    hits = [
        {"clause_id": "FAR-52.212-4", "title": "Contract Terms and Conditions",
         "score": 0.91, "far_part": "FAR"},
        {"clause_id": "DFARS-252.204-7012", "title": "Safeguarding Covered Defense Information",
         "score": 0.87, "far_part": "DFARS"},
    ][: req.top_k]
    return {
        "query": req.query,
        "hits": hits,
        "synthesis": bedrock["body"],
        "model": BEDROCK_MODEL_ID,
    }


@app.post("/eval/factor-suggest")
def eval_factor_suggest(req: FactorSuggestRequest) -> dict[str, Any]:
    """
    Section M factor-narrative suggestion. HITL-gated by evaluator.

    ⚠ Item 4 — no Pydantic response model.
    ⚠ Item 6 — no correlation-id forwarded.
    """
    log.info("eval/factor-suggest topic=%r", req.topic)
    bedrock = invoke_model(
        f"Suggest a Section M factor narrative for: {req.topic}. "
        f"Proposal context: {req.constraints or '(none)'}",
        system="You suggest evaluator narrative; HITL approves before publish.",
    )
    return {
        "narrative_suggestion": bedrock["body"],
        "hitl_gate": "evaluator-review-required",
        "model": BEDROCK_MODEL_ID,
    }


@app.post("/eval/ssdd-draft")
def eval_ssdd_draft(req: DraftRequest) -> dict[str, Any]:
    """
    Source Selection Decision Document tradeoff narrative drafting.
    SSA-gated (FAR 15.308 — non-delegable).

    ⚠ Item 4 — no Pydantic response model.
    ⚠ Item 6 — no correlation-id forwarded.
    """
    log.info("eval/ssdd-draft topic=%r", req.topic)
    bedrock = invoke_model(
        f"Draft an SSDD tradeoff narrative for: {req.topic}. "
        f"Constraints: {req.constraints or 'best-value-tradeoff per FAR 15.101-1'}.",
        system="You draft Source Selection Decision Documents; SSA reviews + signs.",
    )
    # Provide a clause_id field so evaluation-service can stash it.
    return {
        "ssdd_narrative": bedrock["body"],
        "clause_id": f"SSDD-{random.randint(1000, 9999)}",
        "hitl_gate": "ssa-signature-required",
        "model": BEDROCK_MODEL_ID,
    }


@app.post("/agent/intake-triage")
def agent_intake_triage(req: IntakeTriageRequest) -> dict[str, Any]:
    """
    Multi-agent W3 flow: triage incoming proposal, route to TEP evaluators,
    escalate anomalies to CO.

    Sequential agent invocations (intake-classifier → evaluator-router →
    anomaly-escalator); each call is currently a single Bedrock invoke
    with the same stub fallback. LangGraph wiring comes in W3.

    ⚠ Item 4 — no Pydantic response model.
    ⚠ Item 6 — no correlation-id forwarded; each agent hop is invisible in
       the audit log because nothing threads a request id through.
    """
    log.info("agent/intake-triage proposal_id=%r", req.proposal_id)
    classify = invoke_model(
        f"Classify this proposal's NAICS + complexity: {req.raw_text or req.proposal_id}",
        system="You classify federal proposals for TEP routing.",
    )
    route = invoke_model(
        f"Recommend 3 TEP evaluators for proposal_id={req.proposal_id}.",
        system="You route proposals to TEP members based on factor expertise.",
    )
    anomaly = invoke_model(
        f"Flag anomalies in proposal_id={req.proposal_id} that warrant CO escalation.",
        system="You flag anomalies (responsiveness, eligibility, set-aside).",
    )
    return {
        "proposal_id": req.proposal_id,
        "classification": classify["body"],
        "routing": route["body"],
        "anomalies": anomaly["body"],
        "escalation_required": "CO" if "anomaly" in anomaly["body"].lower() else None,
        "hitl_gate": "co-review-on-escalation",
        "model": BEDROCK_MODEL_ID,
    }


