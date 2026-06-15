"""Centralized ChatBedrockConverse construction (DEMO-REDESIGN-spec §1).

Every model call in the orchestrator goes through ``build_chat`` so the
cost-runaway guards — ``max_tokens`` (per-turn output ceiling) and
``max_retries`` (boto3 retry-storm cap) — are applied uniformly instead of
drifting across six construction sites.

This does NOT replace the recursion_limit guard: per-turn output caps bound a
single generation; ``recursion_limit`` (passed at each agent invoke) bounds the
number of turns. Both are required — the 2026-06-12 incident was an unbounded
turn count, not an oversized single turn.

The per-agent factory functions (``_harness_chat``, ``_draft_chat``,
``_extract_chat``, ``_critic_chat``) remain as test seams; they delegate here.
"""
from __future__ import annotations

from app import config


def build_chat(model: str, *, max_tokens: int):
    """Construct a guarded ChatBedrockConverse. Lazy import keeps boto3 out of
    unit-test import paths (factories are monkeypatched there)."""
    from langchain_aws import ChatBedrockConverse  # noqa: PLC0415 — lazy

    return ChatBedrockConverse(
        model=model,
        max_tokens=max_tokens,
        max_retries=config.BEDROCK_MAX_RETRIES,
    )
