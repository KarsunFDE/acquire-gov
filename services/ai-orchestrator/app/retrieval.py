"""M2 retrieval factory + query classifier.

Spec: docs/specs/m2-retrieval-pipeline.md §5 (retrieval.py owns
``build_far_retriever`` + classifier).
ADRs: ADR-0006 D3-D4 (per-query RRF weights), ADR-0008 D2 (tenant
isolation factory layer).

The factory is the **only** sanctioned construction site for the hybrid
retriever. Direct construction of ``MongoDBAtlasHybridSearchRetriever``
outside this module is review-blocking (m2-retrieval-pipeline.md §7
factory layer).
"""
from __future__ import annotations

import re
from typing import Any

from app import config


# Acronyms that should bias toward BM25 lexical match (ADR-0006 D3 table).
# Curated list — keep narrow; acronym ambiguity bloats false positives.
_ACRONYMS: frozenset[str] = frozenset({
    "SBSA", "IDIQ", "LPTA", "FBO", "SDVOSB", "WOSB", "HUBZONE",
    "FAR", "DFARS", "CPFF", "FFP", "BPA", "RFP", "RFQ", "RFI", "COTS",
})

# Matches FAR/DFARS clause-number forms: NN.NNN or NN.NNN-N (ADR-0006 D3).
_CLAUSE_RE = re.compile(r"\b\d{2}\.\d{3}(?:-\d+)?\b")

# Tokenizer for acronym + word-count detection.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")


def classify_query(query: str) -> tuple[float, float]:
    """Return ``(vector_weight, fulltext_weight)`` per ADR-0006 D3.

    Rules (first match wins):
      - Clause-number regex hit ``\\d{2}\\.\\d{3}(-\\d+)?`` → (0.5, 2.0)
      - Known acronym (case-insensitive) → (0.5, 2.0)
      - Semantic phrase > 8 words → (1.5, 0.7)
      - Default → (1.0, 1.0)

    Never raises. Empty / non-string input falls through to default.
    """
    if not query:
        return (1.0, 1.0)

    if _CLAUSE_RE.search(query):
        return (0.5, 2.0)

    tokens = _WORD_RE.findall(query)
    upper_tokens = {t.upper() for t in tokens}
    if upper_tokens & _ACRONYMS:
        return (0.5, 2.0)

    if len(tokens) > 8:
        return (1.5, 0.7)

    return (1.0, 1.0)


def _get_vector_store() -> Any:
    """Resolve a langchain-mongodb VectorStore instance.

    Real construction lands with C9 endpoint wiring (m2-retrieval-pipeline
    §12). Until then, this returns ``None`` so the factory contract is
    testable via mock injection without requiring atlas-local to be up.

    Tests override via ``monkeypatch.setattr(retrieval, "_get_vector_store",
    lambda: <mock>)``.
    """
    return None


def build_far_retriever(
    *,
    tenant_id: str,
    vector_weight: float = 1.0,
    fulltext_weight: float = 1.0,
) -> Any:
    """Construct the hybrid retriever with mandatory tenant pre-filter.

    REQ-RAG-3 isolation: ``tenant_id`` is keyword-only and required. No
    default, no positional fallback. The pre-filter on ``tenant_id`` runs
    before ANN scan (ADR-0008 D2 structural layer; index DDL in seed/).

    Per-query RRF weights flow from ``classify_query``; defaults preserve
    the equal-weight contract for callers that bypass the classifier
    (e.g., eval harness baselines).
    """
    if not tenant_id:
        raise ValueError(
            "tenant_id is required — REQ-RAG-3 isolation cannot be bypassed"
        )

    # Lazy import — langchain-mongodb is a runtime dep but tests run
    # against mocks; importing at module load breaks pytest collection on
    # dev machines that haven't installed the wheel yet.
    from langchain_mongodb.retrievers import (  # noqa: PLC0415
        MongoDBAtlasHybridSearchRetriever,
    )

    vector_store = _get_vector_store()
    return MongoDBAtlasHybridSearchRetriever(
        vectorstore=vector_store,
        search_index_name=config.SEARCH_INDEX_NAME,
        k=config.RETRIEVAL_K_CANDIDATES,
        vector_weight=vector_weight,
        fulltext_weight=fulltext_weight,
        pre_filter={"tenant_id": tenant_id},
    )
