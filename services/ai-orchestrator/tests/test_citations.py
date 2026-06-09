"""C7 — citation hard-fail verification (ADR-0011 D3).

Spec: docs/specs/m2-retrieval-pipeline.md §3 stage 11, §9.
"""
from __future__ import annotations

import pytest

from app.citations import CitationVerificationFailed, verify_citations


# --- Pass path -------------------------------------------------------------

def test_all_cited_ids_in_retrieved_returns_true() -> None:
    retrieved = [{"_id": "c1", "text": "..."}, {"_id": "c2", "text": "..."}]
    generation = {"citations": [{"chunk_id": "c1"}, {"chunk_id": "c2"}]}
    assert verify_citations(generation, retrieved) is True


def test_subset_citations_are_ok() -> None:
    """Generation citing fewer than all retrieved chunks is fine."""
    retrieved = [{"_id": "c1"}, {"_id": "c2"}, {"_id": "c3"}]
    generation = {"citations": [{"chunk_id": "c1"}]}
    assert verify_citations(generation, retrieved) is True


def test_empty_citations_passes_trivially() -> None:
    retrieved = [{"_id": "c1"}]
    generation = {"citations": []}
    assert verify_citations(generation, retrieved) is True


def test_missing_citations_key_passes_trivially() -> None:
    retrieved = [{"_id": "c1"}]
    generation: dict = {}
    assert verify_citations(generation, retrieved) is True


# --- Fail path -------------------------------------------------------------

def test_unknown_id_raises_citation_verification_failed() -> None:
    retrieved = [{"_id": "c1"}]
    generation = {"citations": [{"chunk_id": "c1"}, {"chunk_id": "ghost"}]}
    with pytest.raises(CitationVerificationFailed) as exc_info:
        verify_citations(generation, retrieved)
    assert exc_info.value.unknown_ids == ["ghost"]


def test_multiple_unknown_ids_all_reported_sorted() -> None:
    retrieved = [{"_id": "c1"}]
    generation = {
        "citations": [
            {"chunk_id": "c1"},
            {"chunk_id": "zzz"},
            {"chunk_id": "aaa"},
        ]
    }
    with pytest.raises(CitationVerificationFailed) as exc_info:
        verify_citations(generation, retrieved)
    assert exc_info.value.unknown_ids == ["aaa", "zzz"]


# --- ID-normalization (chunk_id vs _id) -----------------------------------

def test_retrieved_chunks_with_chunk_id_form_also_match() -> None:
    """Retrieved chunks coming from rerank carry ``chunk_id`` (mapped),
    not raw Mongo ``_id``. Verifier accepts both."""
    retrieved = [{"chunk_id": "c1"}, {"chunk_id": "c2"}]
    generation = {"citations": [{"chunk_id": "c1"}]}
    assert verify_citations(generation, retrieved) is True


def test_string_coercion_of_ids() -> None:
    """ObjectId-like vs str comparison: verifier coerces to str."""
    retrieved = [{"_id": 12345}, {"_id": "c2"}]
    generation = {"citations": [{"chunk_id": "12345"}]}
    assert verify_citations(generation, retrieved) is True
