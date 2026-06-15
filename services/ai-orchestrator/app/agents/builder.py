"""Section-drafter agent factory (design ref §7).

Single factory invoked by ``api/draft.py`` per request. Agent construction is
cheap (no model warmup beyond ChatBedrockConverse's lazy boto3 client); the
checkpointer is the process-wide singleton from ``agents.checkpointer``.

LangChain anchor: v1.0 ``langchain.agents.create_agent``. Pre-v1.0 patterns
(PromptTemplate, legacy chain ``.run()``, LCEL pipe chains) are
review-blocking here (design ref §1).
"""
from __future__ import annotations

from app import config
from app.agents.checkpointer import build_mongodb_saver
from app.agents.middleware.hitl_gate import build_hitl_middleware
from app.agents.prompts import SECTION_DRAFTING_SYSTEM_PROMPT
from app.agents.schemas import FinalDraftSection
from app.agents.tools import (
    compute_gate_decision,
    draft_section_text,
    extract_section_requirements,
    retrieve_far_clauses,
    retrieve_related_solicitations,
    validate_citations,
)

SECTION_DRAFTER_TOOLS = [
    retrieve_far_clauses,
    retrieve_related_solicitations,
    extract_section_requirements,
    compute_gate_decision,
    draft_section_text,
    validate_citations,
]


def _harness_chat():
    """Harness model factory — tests monkeypatch this."""
    from app.agents.model_factory import build_chat  # noqa: PLC0415 — lazy

    return build_chat(config.BEDROCK_GEN_MODEL, max_tokens=config.BEDROCK_GEN_MAX_TOKENS)


def build_section_drafter_agent():
    """Construct the v1.0 agent per ADR-0012 D1/D3/D4/D6."""
    from langchain.agents import create_agent  # noqa: PLC0415 — lazy
    from langchain.agents.structured_output import ToolStrategy  # noqa: PLC0415

    middleware = [m for m in (build_hitl_middleware(),) if m is not None]
    return create_agent(
        model=_harness_chat(),
        tools=SECTION_DRAFTER_TOOLS,
        system_prompt=SECTION_DRAFTING_SYSTEM_PROMPT,
        # D3 — structured output. ToolStrategy (not provider-native): Claude on
        # Converse compiles a constrained-decoding grammar over ALL tool schemas
        # for native structured output and rejects this agent's six-tool set
        # with "compiled grammar is too large".
        response_format=ToolStrategy(FinalDraftSection),
        middleware=middleware,                        # D6 (interrupts: Phase 2)
        checkpointer=build_mongodb_saver(),           # D4
        name="section_drafter",                       # LangSmith run name
    )
