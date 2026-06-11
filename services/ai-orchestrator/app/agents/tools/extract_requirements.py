"""``extract_section_requirements`` — LLM tool on the extractor model (design ref §8.3).

The only LLM call not running through the agent harness — it invokes
``ChatBedrockConverse`` directly with ``with_structured_output`` on the
lightweight extractor model (Nova Lite by default; ~50× cheaper per input
token than Sonnet). This is the documented v1.0 "outside-of-agents"
structured-output path; calling it from a tool body is functionally
outside-of-agents.

Failure policy (ADR-0012 D3): structured-output parse failure retries
``BEDROCK_EXTRACT_MAX_RETRIES`` times with the same prompt; final failure
returns ``requirements=[]`` (degraded — agent treats raw user_constraints as
a supplemental hint). Never a terminal raise.
"""
from __future__ import annotations

import hashlib
import logging

from langchain.tools import tool
from pydantic import BaseModel, ConfigDict, ValidationError

from app import config
from app.agents.schemas import ExtractedRequirements, Requirement

log = logging.getLogger("ai-orchestrator.tools.extract_requirements")


class _ExtractPayload(BaseModel):
    """Model-facing inner schema — the LLM emits only the requirement rows;
    the tool wraps them with hash/model/token metadata."""

    model_config = ConfigDict(extra="forbid")

    requirements: list[Requirement]


def _extract_chat():
    """Factory — tests monkeypatch this."""
    from langchain_aws import ChatBedrockConverse  # noqa: PLC0415 — lazy

    return ChatBedrockConverse(model=config.BEDROCK_EXTRACT_MODEL)


def _extract_prompt(user_constraints: str, section_id: str) -> str:
    return (
        f"Extract structured solicitation requirements from the contracting "
        f"officer's free-text constraints below, for FAR UCF Section {section_id}.\n"
        f"Classify each as must (binding) or should (preference). Include a FAR "
        f"clause hint only when the text names or clearly implies one. source_span "
        f"is the [start, end) character offsets of the supporting span.\n\n"
        f"Constraints:\n{user_constraints}"
    )


def _empty(user_constraints: str | None) -> ExtractedRequirements:
    return ExtractedRequirements(
        requirements=[],
        source_text_hash=(
            hashlib.sha256(user_constraints.encode("utf-8")).hexdigest()
            if user_constraints
            else ""
        ),
        model=config.BEDROCK_EXTRACT_MODEL,
        input_tokens=0,
        output_tokens=0,
    )


@tool
def extract_section_requirements(
    user_constraints: str | None,
    section_id: str,
) -> ExtractedRequirements:
    """Extract structured requirements from CO free-text constraints.

    Call this only when user_constraints is non-null; skip otherwise.
    On extraction failure the result is empty — treat the raw constraints
    as a supplemental drafting hint in that case.
    """
    if not user_constraints:
        return _empty(user_constraints)

    extractor = _extract_chat().with_structured_output(_ExtractPayload, include_raw=True)
    prompt = _extract_prompt(user_constraints, section_id)
    last_exc: Exception | None = None
    for attempt in range(config.BEDROCK_EXTRACT_MAX_RETRIES + 1):
        try:
            result = extractor.invoke(prompt)
            parsed: _ExtractPayload | None = result.get("parsed")
            if parsed is None:
                raise ValueError(result.get("parsing_error") or "structured output parse failed")
            raw = result.get("raw")
            usage = getattr(raw, "usage_metadata", None) or {}
            return ExtractedRequirements(
                requirements=parsed.requirements,
                source_text_hash=hashlib.sha256(
                    user_constraints.encode("utf-8")
                ).hexdigest(),
                model=config.BEDROCK_EXTRACT_MODEL,
                input_tokens=int(usage.get("input_tokens", 0) or 0),
                output_tokens=int(usage.get("output_tokens", 0) or 0),
            )
        except (ValidationError, ValueError) as exc:
            last_exc = exc
            log.warning(
                "extract_section_requirements parse failure (attempt %d/%d): %s",
                attempt + 1, config.BEDROCK_EXTRACT_MAX_RETRIES + 1, exc,
            )
    log.warning("extract_section_requirements degraded to empty: %s", last_exc)
    return _empty(user_constraints)
