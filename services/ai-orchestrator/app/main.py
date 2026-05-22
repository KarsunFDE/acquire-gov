"""
ai-orchestrator — main FastAPI entrypoint.

DELIBERATE BROWNFIELD DEBT (annotated for cohort discovery):

  Item 4 — No structured-output validation. /draft-solicitation returns the
           raw stub response (sometimes {"clause_id": null, ...}); downstream
           Spring service hits NullPointerException on .clause_id.toString().

  Item 5 (partial) — This file uses the LangChain v1.0+ composed-Runnable
           pattern (prompt | llm | parser). The legacy LLMChain(...).run(...)
           pattern lives in app/legacy_chain.py. Cohort consolidates in W2.

  Item 6 (partial) — No correlation-ID logging at all. Other services log
           X-Request-ID / correlationId / traceId — this one logs nothing.

  Item 7 — pinecone-client is in requirements.txt but no `import pinecone`
           anywhere. Cohort removes in W2.

  Item 11 — Dockerfile uses :latest.

  Plus: no retry, no streaming, no real Bedrock invocation in this stub.
"""
from __future__ import annotations

import json
import logging
import os
import random
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ⚠ Item 5 — v1.0 composed-Runnable style. Imported but not actually wired to
# Bedrock in the stub (we return mock data). Cohort wires it up in W1 Thu.
try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    _LANGCHAIN_V1_AVAILABLE = True
except ImportError:
    _LANGCHAIN_V1_AVAILABLE = False

# Note: legacy_chain.py also exists in this package and uses the pre-v1.0
# LLMChain pattern. Item 5 — cohort migrates that file's style to this one.

# ⚠ DELIBERATE — no correlation-ID in the log format (Item 6).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s - %(message)s",
)
log = logging.getLogger("ai-orchestrator")

app = FastAPI(title="ai-orchestrator", version="0.1.0-brownfield")

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-7-sonnet-20250219-v1:0"
)
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


class DraftRequest(BaseModel):
    """
    ⚠ DELIBERATE — Item 4 reinforcement:
      No Field constraints, no examples, no descriptions. Cohort tightens
      in W1 Fri output validation.
    """
    topic: str
    constraints: str | None = None


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
    Bedrock invocation stub for solicitation drafting.

    Returns a mock structured-ish response so the rest of the stack can be
    exercised without real AWS creds.

    ⚠ DELIBERATE GAPS (Item 4):
      - No Pydantic response model — returns raw dict.
      - 1-in-3 calls return {"clause_id": null, ...} to exercise the
        downstream NullPointerException path.
      - No retry, no streaming, no cost tracking, no structured-output
        schema enforced.
    """
    log.info("draft-solicitation called topic=%r constraints=%r",
             req.topic, req.constraints)

    # ⚠ Item 4 — 1-in-3 returns null clause_id; downstream service can break.
    if random.randint(1, 3) == 1:
        return {
            "clause_id": None,  # ← will trigger downstream NPE
            "draft": f"[stub] draft about {req.topic}",
            "model": BEDROCK_MODEL_ID,
        }

    # Otherwise return a "happy" stub.
    return {
        "clause_id": f"FAR-52.{random.randint(200, 250)}-{random.randint(1, 30)}",
        "draft": f"[stub] draft about {req.topic}. Constraints: {req.constraints or 'none'}.",
        "model": BEDROCK_MODEL_ID,
        "region": AWS_REGION,
    }


@app.post("/draft-solicitation-v1")
def draft_solicitation_v1(req: DraftRequest) -> dict[str, Any]:
    """
    v1.0 composed-Runnable example (Item 5).

    Demonstrates the prompt | llm | parser pattern the cohort migrates the
    legacy_chain.py to in W2. Still a stub — doesn't hit real Bedrock.
    """
    if not _LANGCHAIN_V1_AVAILABLE:
        raise HTTPException(503, "langchain v1.0 not available")

    # Composed-Runnable scaffolding — would be:
    #   prompt | bedrock_llm | StrOutputParser()
    # We just demonstrate the construction without invoking it.
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You draft federal acquisition clauses."),
        ("user", "Draft a paragraph about: {topic}. Constraints: {constraints}."),
    ])
    parser = StrOutputParser()
    _chain_scaffold = prompt | parser  # would normally be: prompt | llm | parser

    log.info("draft-solicitation-v1 (composed Runnable scaffold) topic=%r",
             req.topic)

    return {
        "clause_id": f"FAR-52.{random.randint(200, 250)}-{random.randint(1, 30)}",
        "draft": f"[stub-v1] composed-runnable draft about {req.topic}",
        "model": BEDROCK_MODEL_ID,
        "pattern": "prompt | llm | parser",
    }
