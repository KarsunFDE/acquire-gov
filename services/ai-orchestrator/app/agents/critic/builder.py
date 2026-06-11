"""Consistency-critic agent factory (design ref §18.4).

NO middleware (critic never interrupts — warn-only Phase 1) and NO
checkpointer (critic runs are short; no multi-day pause).
"""
from __future__ import annotations

from app import config
from app.agents.critic.prompts import CONSISTENCY_CRITIC_SYSTEM_PROMPT
from app.agents.critic.tools import (
    check_clin_coverage,
    check_set_aside_consistency,
    verify_l_m_consistency,
)
from app.agents.schemas import ConsistencyReport

CRITIC_TOOLS = [
    verify_l_m_consistency,
    check_set_aside_consistency,
    check_clin_coverage,
]


def _critic_harness_chat():
    """Harness model factory — tests monkeypatch this."""
    from langchain_aws import ChatBedrockConverse  # noqa: PLC0415 — lazy

    return ChatBedrockConverse(model=config.BEDROCK_CRITIC_MODEL)


def build_consistency_critic_agent():
    from langchain.agents import create_agent  # noqa: PLC0415 — lazy

    return create_agent(
        model=_critic_harness_chat(),
        tools=CRITIC_TOOLS,
        system_prompt=CONSISTENCY_CRITIC_SYSTEM_PROMPT,
        response_format=ConsistencyReport,
        name="consistency_critic",
    )
