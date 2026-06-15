"""``retrieve_far_clauses`` — programmatic retrieval tool (design ref §8.1).

Wraps M2's ``build_far_retriever`` (tenant pre-filter is structural — the agent
cannot bypass it; tenant_id comes from RunnableConfig, never from tool args)
plus the new ``rerank.rerank_only`` split (§8.1.1).
"""
from __future__ import annotations

import logging
from datetime import date

from langchain_core.runnables import RunnableConfig
from langchain.tools import tool

from app import rerank, retrieval
from app.agents.schemas import Chunk, RetrievedEvidence

log = logging.getLogger("ai-orchestrator.tools.retrieve_far")

_EPOCH = date(1970, 1, 1)


def _to_chunk(c: dict) -> Chunk:
    raw_date = c.get("snapshot_date") or _EPOCH
    return Chunk(
        chunk_id=str(c.get("chunk_id") or c.get("_id") or ""),
        text=c.get("text", ""),
        far_part=str(c.get("far_part", "")),
        far_section=str(c.get("far_section", "")),
        far_clause=c.get("far_clause"),
        snapshot_date=raw_date,
        relevance_score=float(c.get("relevance_score", 0.0)),
    )


@tool
def retrieve_far_clauses(
    query: str,
    k: int = 20,
    *,
    config: RunnableConfig,
) -> RetrievedEvidence:
    """Retrieve FAR clauses relevant to `query`.

    Returns up to `k` reranked chunks plus the rerank top score. Call this
    before any drafting tool — without retrieval, every authoritative claim
    you produce is ungrounded. Tenant pre-filter is enforced structurally by
    the retriever factory; you cannot bypass it.
    """
    tenant_id = config["configurable"]["tenant_id"]  # set by handler at invoke time
    vector_w, fulltext_w = retrieval.classify_query(query)
    retriever = retrieval.build_far_retriever(
        tenant_id=tenant_id, vector_weight=vector_w, fulltext_weight=fulltext_w
    )
    candidates = list(retriever.invoke(query))[:k]
    reranked = rerank.rerank_only(query, candidates)
    return RetrievedEvidence(
        chunks=[_to_chunk(c) for c in reranked.top],
        vector_weight=vector_w,
        fulltext_weight=fulltext_w,
        rerank_top_score=reranked.top_score,  # None on rerank outage
        degraded_mode=reranked.degraded_mode,
    )
