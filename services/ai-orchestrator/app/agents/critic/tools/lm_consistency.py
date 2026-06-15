"""``verify_l_m_consistency`` — LLM critic tool (ADR-0014 D5).

Renamed from ``check_l_m_alignment`` (ADR-0013): FAR 15.204-5 does NOT mandate
L↔M alignment in regulation text — this is a best-practice + bid-protest
pattern check. On the batch path PartIVDrafter drafts L+M together so the
alignment is built-in and this tool verifies it; on the standalone Step 12
path L and M may be hand-typed, so the LLM semantic check is the only
alignment surface. The same tool body handles both — the difference is the
text it sees.

Severity semantics per ADR-0014 D5: ``l_without_m`` / ``m_without_l`` are
``fail`` (rare-by-construction on the batch path); ``weak_mapping`` is
``warn``. Phase 1 aggregation still clamps the OVERALL report to warn (D5).
Single-pass — malformed structured output propagates (no retry; critic runs
are cheap to re-trigger from Step 12).
"""
from __future__ import annotations

import logging
from typing import Literal

from langchain.tools import tool
from pydantic import BaseModel, ConfigDict

from app import config
from app.agents.schemas import LMAlignmentReport, LMMismatch

log = logging.getLogger("ai-orchestrator.critic.lm")


class LMFindingsPayload(BaseModel):
    """Model-facing inner schema — mismatch findings ONLY. Everything
    derivable (overall_severity) or bookkeeping (model/tokens) is computed
    by the tool; Nova Lite omits any field it considers secondary."""

    model_config = ConfigDict(extra="forbid")

    mismatches: list[LMMismatch]


_SEVERITY_ORDER = {"info": 0, "warn": 1, "fail": 2}


def _max_severity(mismatches: list[LMMismatch]) -> Literal["info", "warn", "fail"]:
    if not mismatches:
        return "info"
    return max((m.severity for m in mismatches), key=_SEVERITY_ORDER.__getitem__)


def _critic_chat():
    """Factory — tests monkeypatch this."""
    from app.agents.model_factory import build_chat  # noqa: PLC0415 — lazy

    return build_chat(config.BEDROCK_CRITIC_MODEL, max_tokens=config.BEDROCK_CRITIC_MAX_TOKENS)


def _lm_alignment_prompt(section_l: str, section_m: str) -> str:
    return (
        "You are checking a federal solicitation for FAR 15.204-5 best-practice "
        "alignment between Section L (Instructions to Offerors) and Section M "
        "(Evaluation Factors).\n\n"
        "Rules:\n"
        "- Every L instruction requiring offerors to submit/address something "
        "should map to an M factor that evaluates it → otherwise emit a "
        "mismatch of type l_without_m with severity fail.\n"
        "- Every M factor should have a corresponding L instruction telling "
        "offerors what to submit → otherwise emit m_without_l with severity fail.\n"
        "- Vague or partial mappings → weak_mapping with severity warn.\n"
        "- No issues → mismatches=[].\n\n"
        f"SECTION L:\n{section_l}\n\nSECTION M:\n{section_m}"
    )


@tool
def verify_l_m_consistency(
    section_l: str | None, section_m: str | None
) -> LMAlignmentReport:
    """Check FAR 15.204-5 L↔M coherence: every Section L instruction maps to a
    Section M evaluation factor and vice versa.

    Call this exactly once with the solicitation's Section L and Section M
    text (null when a section is missing).
    """
    if not section_l or not section_m:
        return LMAlignmentReport(
            mismatches=[
                LMMismatch(
                    type="l_without_m" if not section_m else "m_without_l",
                    l_instruction=None,
                    m_factor=None,
                    severity="info",
                    rationale="one section missing — skipping semantic check",
                )
            ],
            overall_severity="info",
            model=config.BEDROCK_CRITIC_MODEL,
            input_tokens=0,
            output_tokens=0,
        )
    chat = _critic_chat().with_structured_output(LMFindingsPayload, include_raw=True)
    result = chat.invoke(_lm_alignment_prompt(section_l, section_m))
    parsed: LMFindingsPayload | None = result.get("parsed")
    if parsed is None:
        # Single-pass critic — no fallback (design ref §18.8 test note).
        raise ValueError(
            f"critic_parse_failed: {result.get('parsing_error') or 'malformed structured output'}"
        )
    raw = result.get("raw")
    usage = getattr(raw, "usage_metadata", None) or {}
    return LMAlignmentReport(
        mismatches=parsed.mismatches,
        overall_severity=_max_severity(parsed.mismatches),
        model=config.BEDROCK_CRITIC_MODEL,
        input_tokens=int(usage.get("input_tokens", 0) or 0),
        output_tokens=int(usage.get("output_tokens", 0) or 0),
    )
