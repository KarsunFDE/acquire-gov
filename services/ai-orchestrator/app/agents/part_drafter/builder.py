"""PartDrafterAgent factory (ADR-0014; design ref §18.12.2).

A SEPARATE factory from ``agents.builder.build_section_drafter_agent`` (which
stays exactly as ADR-0012 wrote it — D8). Same tool surface; different system
prompt + structured output (PartDraftBundle instead of FinalDraftSection).
"""
from __future__ import annotations

from typing import Literal

from app import config
from app.agents.checkpointer import build_mongodb_saver
from app.agents.middleware.hitl_gate import build_hitl_middleware
from app.agents.part_drafter.prompts import PART_DRAFTING_SYSTEM_PROMPTS
from app.agents.schemas import PartDraftBundle
from app.agents.tools import (
    compute_gate_decision,
    draft_section_text,
    extract_section_requirements,
    retrieve_far_clauses,
    retrieve_related_solicitations,
    validate_citations,
)

PART_DRAFTER_TOOLS = [
    retrieve_far_clauses,
    retrieve_related_solicitations,
    extract_section_requirements,
    compute_gate_decision,
    draft_section_text,
    validate_citations,
]


def _harness_chat():
    """Harness model factory — tests monkeypatch this."""
    from langchain_aws import ChatBedrockConverse  # noqa: PLC0415 — lazy

    return ChatBedrockConverse(model=config.BEDROCK_GEN_MODEL)


def build_part_drafter_agent(part: Literal["I", "IV"]):
    from langchain.agents import create_agent  # noqa: PLC0415 — lazy

    middleware = [m for m in (build_hitl_middleware(),) if m is not None]
    return create_agent(
        model=_harness_chat(),
        tools=PART_DRAFTER_TOOLS,
        system_prompt=PART_DRAFTING_SYSTEM_PROMPTS[part],
        response_format=PartDraftBundle,
        middleware=middleware,
        checkpointer=build_mongodb_saver(),
        name=f"part_{part.lower()}_drafter",
    )
