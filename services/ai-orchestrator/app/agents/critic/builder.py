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
    from app.agents.model_factory import build_chat  # noqa: PLC0415 — lazy

    return build_chat(config.BEDROCK_CRITIC_MODEL, max_tokens=config.BEDROCK_CRITIC_MAX_TOKENS)


def build_consistency_critic_agent():
    from langchain.agents import create_agent  # noqa: PLC0415 — lazy
    from langchain.agents.structured_output import ToolStrategy  # noqa: PLC0415

    return create_agent(
        model=_critic_harness_chat(),
        tools=CRITIC_TOOLS,
        system_prompt=CONSISTENCY_CRITIC_SYSTEM_PROMPT,
        # ToolStrategy — see section builder note on Converse grammar limits.
        response_format=ToolStrategy(ConsistencyReport),
        name="consistency_critic",
    )
