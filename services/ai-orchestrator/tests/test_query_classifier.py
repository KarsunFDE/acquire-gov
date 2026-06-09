"""C5 — query classifier per-query RRF weights (ADR-0006 D3).

Spec: docs/specs/m2-retrieval-pipeline.md §3 stage 4, §5
(retrieval.py owns regex/keyword classifier per ADR-0006 D3 table).
ADR: ADR-0006 D3 — per-query weight rules.

Branches covered:
  - Clause-number regex hit → (0.5, 2.0)
  - Known acronym hit       → (0.5, 2.0)
  - >8 word semantic phrase → (1.5, 0.7)
  - Default                 → (1.0, 1.0)
"""
from __future__ import annotations

import pytest

from app.retrieval import classify_query


# --- Clause-number regex branch --------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "What does FAR 15.305 say?",
        "Explain 52.212-4",
        "Compare 15.305 and 15.308",
        "DFARS 252.204-7012",  # acronym + clause — clause wins (first match)
        "Reference 12.345-99 carefully",
    ],
)
def test_clause_number_biases_to_fulltext(query: str) -> None:
    """Clause-number form gets BM25 weight 2.0; vector weight halved."""
    assert classify_query(query) == (0.5, 2.0)


# --- Known-acronym branch --------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "What is an IDIQ?",
        "Define SDVOSB eligibility",
        "Explain LPTA tradeoffs",
        "lowercase rfp works too",
        "RFI vs RFQ vs RFP",
        "HUBZONE set-aside rules",
        "COTS procurement basics",
    ],
)
def test_acronym_biases_to_fulltext(query: str) -> None:
    assert classify_query(query) == (0.5, 2.0)


# --- Semantic-phrase branch (>8 words) -------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        # 12 words.
        "Describe how source selection authority weighs price against "
        "technical merit during competitive negotiation",
        # 9 words exactly.
        "Tell me about evaluation factors used in source selection plans",
    ],
)
def test_long_semantic_phrase_biases_to_vector(query: str) -> None:
    """>8 words → vector_weight 1.5, fulltext 0.7 (ADR-0006 D3)."""
    assert classify_query(query) == (1.5, 0.7)


# --- Default branch --------------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "evaluation factors please",  # short, no acronym, no clause
        "source selection authority",
        "small business set aside",
        "competitive negotiation rules",
    ],
)
def test_default_returns_equal_weights(query: str) -> None:
    assert classify_query(query) == (1.0, 1.0)


# --- Edge cases ------------------------------------------------------------

def test_empty_query_returns_default() -> None:
    assert classify_query("") == (1.0, 1.0)


def test_classifier_never_raises_on_unusual_input() -> None:
    # Whitespace, punctuation-only, multi-line — must not raise.
    for q in ["   ", "...", "\n\n\n", "!@#$%^&*()"]:
        assert classify_query(q) == (1.0, 1.0)


def test_acronym_match_is_case_insensitive() -> None:
    assert classify_query("idiq contract structure") == (0.5, 2.0)
    assert classify_query("IDIQ contract structure") == (0.5, 2.0)


def test_first_match_wins_clause_before_phrase_length() -> None:
    """A long query that also contains a clause-number should still
    return the clause weights (deterministic precedence per ADR-0006 D3)."""
    long_with_clause = (
        "Tell me everything there is to know about FAR 15.305 evaluation "
        "factors"
    )
    assert classify_query(long_with_clause) == (0.5, 2.0)
