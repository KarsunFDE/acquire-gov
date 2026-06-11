"""P1.2 — validate_citations hard-fail tests (design ref §13.1)."""
from __future__ import annotations

import pytest

from app.agents.schemas import ClaimCitation
from app.agents.tools.validate import validate_citations
from app.citations import CitationVerificationFailed


def _claim(chunk_id: str) -> ClaimCitation:
    return ClaimCitation(sentence_index=0, chunk_id=chunk_id)


def _run(claims, retrieved):
    return validate_citations.func(  # type: ignore[attr-defined]
        section_text="text", claim_chunk_map=claims, retrieved_ids=retrieved
    )


def test_happy_path_valid():
    result = _run([_claim("c1"), _claim("c2")], ["c1", "c2", "c3"])
    assert result.valid is True
    assert result.unknown_chunk_ids == []
    assert result.grounding_score == 1.0


def test_unknown_chunk_id_raises():
    with pytest.raises(CitationVerificationFailed) as ei:
        _run([_claim("ghost")], ["c1"])
    assert ei.value.unknown_ids == ["ghost"]


def test_empty_claim_map_is_valid():
    result = _run([], ["c1"])
    assert result.valid is True
