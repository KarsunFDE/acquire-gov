"""``validate_citations`` — programmatic hard-fail tool (design ref §8.6).

Thin wrapper around M2's ``app.citations.verify_citations``. Raises
``CitationVerificationFailed`` on any unknown chunk_id — the harness wraps
the raise into a tool-call error which the handler surfaces as HTTP 422
``citation_verification_failed`` (ADR-0011 D3).
"""
from __future__ import annotations

from langchain.tools import tool

from app.agents.schemas import ClaimCitation, ValidationResult
from app.citations import verify_citations


@tool
def validate_citations(
    section_text: str,
    claim_chunk_map: list[ClaimCitation],
    retrieved_ids: list[str],
) -> ValidationResult:
    """Verify every cited chunk_id is in the retrieved set.

    Call this after drafting, passing the claim_chunk_map from
    draft_section_text and the chunk_ids from retrieve_far_clauses. Produce
    your final response only after this returns valid=True.
    """
    # citations.verify_citations consumes the M2 dict shape; adapt.
    generation_result = {
        "citations": [{"chunk_id": c.chunk_id} for c in claim_chunk_map]
    }
    retrieved = [{"chunk_id": rid} for rid in retrieved_ids]
    verify_citations(generation_result, retrieved)  # raises on unknown ids
    return ValidationResult(valid=True, unknown_chunk_ids=[], grounding_score=1.0)
