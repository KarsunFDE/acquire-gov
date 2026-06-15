"""M2 retrieval factory + query classifier.

Spec: docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §5 (retrieval.py owns
``build_far_retriever`` + classifier).
ADRs: ADR-0006 D3-D4 (per-query RRF weights), ADR-0008 D2 (tenant
isolation factory layer).

The factory is the **only** sanctioned construction site for the hybrid
retriever. Direct construction of ``MongoDBAtlasHybridSearchRetriever``
outside this module is review-blocking (m2-retrieval-pipeline.md §7
factory layer).
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

from app import config

log = logging.getLogger("ai-orchestrator.retrieval")


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


@lru_cache(maxsize=1)
def _get_chunks_collection() -> Any:
    """Singleton handle on the ``chunks`` collection (ADR-0008 D3)."""
    from pymongo import MongoClient  # noqa: PLC0415

    client: Any = MongoClient(config.MONGO_URI)
    return client[config.MONGO_DB][config.CHUNKS_COLLECTION]


@lru_cache(maxsize=1)
def _get_vector_store() -> Any:
    """Resolve the langchain-mongodb VectorStore over ``chunks`` (C9 wiring).

    Embeddings delegate to ``app.bedrock_client`` so the bearer-token auth
    path and the credential-free stub fallback stay in one place.

    Tests override via ``monkeypatch.setattr(retrieval, "_get_vector_store",
    lambda: <mock>)``.
    """
    from langchain_core.embeddings import Embeddings  # noqa: PLC0415
    from langchain_mongodb import MongoDBAtlasVectorSearch  # noqa: PLC0415

    class _BedrockClientEmbeddings(Embeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            from app import bedrock_client  # noqa: PLC0415
            return bedrock_client.embed_documents(texts)

        def embed_query(self, text: str) -> list[float]:
            from app import bedrock_client  # noqa: PLC0415
            return bedrock_client.embed_query(text)

    return MongoDBAtlasVectorSearch(
        collection=_get_chunks_collection(),
        embedding=_BedrockClientEmbeddings(),
        index_name=config.VECTOR_INDEX_NAME,
        text_key="text",
        embedding_key="embedding",
        relevance_score_fn="cosine",
    )


class _ChunkDictRetriever:
    """Invoke adapter — maps langchain ``Document`` results to the chunk-dict
    wire shape every M2/M1 consumer expects (``rerank_only``, ``_to_chunk``).

    Dict results (test fakes, pre-adapter callers) pass through untouched.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    @staticmethod
    def _as_dict(item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return item
        meta = dict(getattr(item, "metadata", None) or {})
        meta["text"] = getattr(item, "page_content", "")
        meta.setdefault("chunk_id", str(meta.get("_id", "")))
        return meta

    def invoke(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        return [self._as_dict(r) for r in self._inner.invoke(query, **kwargs)]


# --- Index DDL + insert helpers (ingest path — spec §8 steps 9-10) ---------

_VECTOR_INDEX_DEFINITION = {
    "fields": [
        {
            "type": "vector",
            "path": "embedding",
            "numDimensions": 512,  # Titan v2 @ 512 (ADR-0005 D1)
            "similarity": "cosine",
        },
        {"type": "filter", "path": "tenant_id"},   # REQ-RAG-3 pre-filter
        {"type": "filter", "path": "doc_class"},
        {"type": "filter", "path": "far_part"},
    ]
}

_SEARCH_INDEX_DEFINITION = {
    "mappings": {
        "dynamic": False,
        "fields": {
            "text": {"type": "string"},
        },
    }
}

_indexes_ensured = False


def ensure_search_indexes() -> None:
    """Create the vector + BM25 search indexes on ``chunks`` if absent.

    Idempotent; atlas-local builds them asynchronously, so a freshly seeded
    corpus may take a few seconds to become queryable.
    """
    global _indexes_ensured
    if _indexes_ensured:
        return
    from pymongo.operations import SearchIndexModel  # noqa: PLC0415

    coll = _get_chunks_collection()
    existing = {ix["name"] for ix in coll.list_search_indexes()}
    if config.VECTOR_INDEX_NAME not in existing:
        coll.create_search_index(SearchIndexModel(
            definition=_VECTOR_INDEX_DEFINITION,
            name=config.VECTOR_INDEX_NAME,
            type="vectorSearch",
        ))
        log.info("created vector search index %s", config.VECTOR_INDEX_NAME)
    if config.SEARCH_INDEX_NAME not in existing:
        coll.create_search_index(SearchIndexModel(
            definition=_SEARCH_INDEX_DEFINITION,
            name=config.SEARCH_INDEX_NAME,
            type="search",
        ))
        log.info("created BM25 search index %s", config.SEARCH_INDEX_NAME)
    _indexes_ensured = True


def find_existing_document(
    *, tenant_id: str, source_doc: str, snapshot_date: str
) -> str | None:
    """Spec §10.1 duplicate probe — existing ``document_id`` or ``None``."""
    row = _get_chunks_collection().find_one(
        {
            "tenant_id": tenant_id,
            "source_doc": source_doc,
            "snapshot_date": snapshot_date,
        },
        {"document_id": 1},
    )
    if row is None:
        return None
    return str(row.get("document_id") or row["_id"])


def bulk_insert_chunks(chunks: list[dict[str, Any]], *, document_id: str) -> None:
    """Spec §8 step 10 — stamp ``document_id`` and bulk-write to ``chunks``."""
    if not chunks:
        return
    ensure_search_indexes()
    _get_chunks_collection().insert_many(
        [{**c, "document_id": document_id} for c in chunks]
    )


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
    inner = MongoDBAtlasHybridSearchRetriever(
        vectorstore=vector_store,
        search_index_name=config.SEARCH_INDEX_NAME,
        k=config.RETRIEVAL_K_CANDIDATES,
        vector_weight=vector_weight,
        fulltext_weight=fulltext_weight,
        pre_filter={"tenant_id": tenant_id},
    )
    return _ChunkDictRetriever(inner)
