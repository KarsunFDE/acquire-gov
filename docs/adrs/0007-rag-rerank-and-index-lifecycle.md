# ADR 0007 — Rerank wiring + index lifecycle + caching

Date: 2026-06-01
Status: Proposed (Phase B of retrieval-system planning)
Decision-makers: FDE pair (delivery lead + author)
Phase: 1 — AI Adoption · Milestone M2 (Grounded Retrieval)
Related: ADR-0005 (foundation stack — rerank model + atlas-local) · ADR-0006 (chunking + per-query pattern) · PRD §6 REQ-RAG-2 (withhold-and-escalate)

## Context

ADR-0005 picked `amazon.rerank-v1:0` ($1/1K queries, us-west-2) as the default reranker with Cohere Rerank 3.5 reserved as escalation. ADR-0006 set the candidate pool size `k=20` from the hybrid retriever. This ADR finalizes (a) when rerank runs and what thresholds gate the response, (b) how vector + BM25 indexes are created, rebuilt, and re-embedded without downtime, and (c) what caching layer Phase 1 ships with.

## Decisions

### D1 — Rerank runs on every M2 grounded-retrieval call

No "skip rerank when score looks good" branch. Phase 1 always reranks because the score returned by rerank IS the withhold-and-escalate signal (PRD REQ-RAG-2). Without a rerank pass, the system has no calibrated confidence number to gate on.

Cost math (per query): hybrid retrieval @ k=20 → rerank 20 docs @ $1/1K queries = **$0.001 per retrieval**. At 10K retrievals/day = $10/day = ~$300/month. Hairpin-budget-acceptable. AWS justifies the spend (https://docs.aws.amazon.com/bedrock/latest/userguide/rerank.html), quoted: *"With a reranker model, you can retrieve fewer, but more relevant, results. By feeding these results to the foundation model that you use to generate a response, you can also decrease cost and latency."* The 5-doc post-rerank cap (D2 below) cuts downstream Sonnet input tokens by ~75% vs feeding all 20 candidates → rerank is net cost-negative end-to-end.

### D2 — top-K = 20, top-N final = 5, two-band threshold gate

Pipeline: hybrid retriever → 20 candidates → `bedrock-agent-runtime.rerank` → 5 results with `relevanceScore`.

Gate on the top result's `relevanceScore`:

| Top score | Action | Rationale |
|---|---|---|
| ≥ 0.5 | **Pass** — return top-5 to agent for grounded generation | High-confidence grounding |
| 0.3 ≤ score < 0.5 | **HITL band** — return results AND emit `requires_human_review=true` flag in response payload | Borderline — generation proceeds but CO sees confidence warning |
| < 0.3 | **Withhold** — return no results; agent must respond "insufficient grounding, escalating" | PRD REQ-RAG-2: "grounded or withheld — no authoritative answer ships without a real citation; weak grounding escalates, never guesses" |

Thresholds (0.3, 0.5) are **starting values**. Phase D eval (RAGAS faithfulness + LLM-as-judge per ADR-0009) tunes them against the eval set. They live in `services/ai-orchestrator/app/config.py` as `RERANK_WITHHOLD_THRESHOLD` and `RERANK_HITL_THRESHOLD` so Phase D can shift them without code changes.

### D3 — Reference implementation

```python
import boto3
from typing import Literal

reranker = boto3.client("bedrock-agent-runtime", region_name="us-west-2")
RERANK_MODEL_ARN = "arn:aws:bedrock:us-west-2::foundation-model/amazon.rerank-v1:0"

def rerank_and_gate(
    query: str,
    candidates: list[dict],
    withhold_threshold: float = 0.3,
    hitl_threshold: float = 0.5,
) -> tuple[Literal["pass", "hitl", "withhold"], list[dict]]:
    if not candidates:
        return "withhold", []

    resp = reranker.rerank(
        queries=[{"type": "TEXT", "textQuery": {"text": query}}],
        sources=[
            {"type": "INLINE",
             "inlineDocumentSource": {"type": "TEXT", "textDocument": {"text": c["text"]}}}
            for c in candidates
        ],
        rerankingConfiguration={
            "type": "BEDROCK_RERANKING_MODEL",
            "bedrockRerankingConfiguration": {
                "modelConfiguration": {"modelArn": RERANK_MODEL_ARN},
                "numberOfResults": 5,
            },
        },
    )
    results = resp["results"]
    top_score = results[0]["relevanceScore"]
    reordered = [candidates[r["index"]] for r in results]

    if top_score < withhold_threshold:
        return "withhold", []
    if top_score < hitl_threshold:
        return "hitl", reordered
    return "pass", reordered
```

`reranker` client uses the same `AWS_BEARER_TOKEN_BEDROCK` auth path as the embed + chat clients — no new auth wiring. The region override (`us-west-2`) is required because Amazon Rerank 1.0 is not available in `us-east-1` (ADR-0005 D2). This is the **only** Bedrock service in the orchestrator that hard-pins a region rather than inheriting from the chat client.

### D4 — Two Atlas Search indexes per tenant collection

Created at seed time via `db.<collection>.createSearchIndex(...)`:

**Vector index** (`far_vector_idx`):
```json
{
  "name": "far_vector_idx",
  "type": "vectorSearch",
  "definition": {
    "fields": [
      { "type": "vector", "path": "embedding",
        "numDimensions": 512, "similarity": "cosine", "quantization": "scalar" },
      { "type": "filter", "path": "tenant_id" },
      { "type": "filter", "path": "far_section" },
      { "type": "filter", "path": "far_clause" }
    ]
  }
}
```

**BM25 / full-text index** (`far_search_idx`):
```json
{
  "name": "far_search_idx",
  "type": "search",
  "definition": {
    "mappings": { "dynamic": true }
  }
}
```

Both indexes live in the same collection (required by `$rankFusion` per https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/) and are consumed by `MongoDBAtlasHybridSearchRetriever` via its `vectorstore` and `search_index_name` constructor params.

**Quantization choice: `scalar`.** Source: https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-quantization/. Storage reduction ~2-4× vs full float32, minimal recall hit. Binary quantization (~32× reduction, higher recall cost) reserved for Phase 1.5 if storage on cloud Atlas becomes a per-month line item that bites. On Atlas Local in dev, storage is essentially free — but scalar still wins on query latency.

### D5 — Zero-downtime rebuild / re-embed lifecycle

Atlas's documented behavior (https://www.mongodb.com/docs/atlas/atlas-vector-search/manage-indexes/), quoted: *"After you edit an index, MongoDB Vector Search rebuilds it. While the index rebuilds, you can continue to run MongoDB Vector Search queries by using the old index definition. When the index finishes rebuilding, the old index is automatically replaced."*

This buys us a clean re-embed path for two future scenarios:

1. **Bumping Titan v2 dims from 512 → 1024** (ADR-0005's documented escalation lever if eval regresses):
   - Re-embed corpus with `dimensions=1024`, write to a NEW field `embedding_1024`.
   - `createSearchIndex` on a NEW index name (`far_vector_idx_v2`) with `path: "embedding_1024", numDimensions: 1024`.
   - Old `far_vector_idx` keeps serving traffic.
   - Once `listSearchIndexes()` shows `status: READY` for v2, flip the retriever to point at the new index (config change, no code change).
   - Drop old index after a safety window.

2. **Swapping embed model entirely** (Phase-2 territory if Cohere Embed v4 or successor wins on eval): same dual-write + flip pattern.

Detection: poll `db.<coll>.listSearchIndexes()` for `status: "READY"` — published in MongoDB docs as the canonical lifecycle field.

### D6 — Caching: Atlas working-set only in Phase 1

Single layer: **Atlas's automatic working-set cache.** Hot index pages stay in RAM; repeated queries on the same chunks hit cache transparently. No application-level cache.

**Why no app-side cache** in Phase 1:
- `langchain-mongodb` has no built-in retrieval cache → app-side cache is **custom code** (guideline-6: don't homegrow).
- LangChain v1 ships `InMemoryCache` / `SQLiteCache` for **LLM responses**, not retriever output — different layer.
- Until observability (Phase D ADR-0009) shows repeated identical retrieval queries hitting frequency that matters, an app-side cache adds infra surface (Redis container or in-process dict + invalidation logic) for unmeasured benefit.

**No "warm-at-boot" eager cache.** Loading the whole FAR corpus into RAM at service startup wastes memory regardless of query mix. Atlas promotes hot pages on actual query load — let it do its job.

Cache promotion path (if and when Phase D observability shows it's needed): wrap `MongoDBAtlasHybridSearchRetriever.invoke` with a small LRU on `(query, tenant_id, weights)` keys. Out of scope for Phase 1.

## Consequences

**Positive:**
- Single rerank model per query gives one calibrated confidence number → REQ-RAG-2 withhold/escalate has a real signal, not an LLM-self-rating proxy.
- Two-band threshold separates "ship" / "ship with warning" / "do not ship" cleanly — gives the HITL surface (ADR-0008) a structured signal.
- Zero-downtime re-embed path means future ADR-0005 D2 escalation (512 → 1024) is a config flip, not a maintenance window.
- Single-layer cache strategy keeps Phase-1 infra surface minimal; promotion lever exists if data justifies it.

**Negative / tradeoffs:**
- Rerank costs ~$0.001/query unconditionally. At extreme low-budget rollouts, a quality-gated bypass ("skip rerank when top hybrid score > X") would save some calls — but loses the calibrated withhold signal. Phase 1 prioritizes the audit-grade signal over the cost optimization; Phase 1.5 can revisit.
- Rerank pins to `us-west-2` while the chat client uses `us.anthropic.…` cross-region inference. Mixing region scopes in one orchestrator request is fine functionally but adds a knob for operators to misconfigure. Compose env var `BEDROCK_RERANK_REGION` is the right way to surface it.
- Atlas's working-set cache is opaque to the application — we cannot prove cache-hit-rate without Atlas server metrics. ADR-0009 (observability) decides whether to scrape those metrics or treat the cache as a black box.

## Verification

- D1/D2: integration test sends a query that should retrieve well (top score ≥ 0.5) → "pass" branch. A query for content not in the corpus → top score < 0.3 → "withhold" branch with empty result list. A near-miss query → "hitl" branch with `requires_human_review=true` in response.
- D3: `bedrock_client.py` test for `rerank_and_gate` using a mocked `bedrock-agent-runtime` client; verify region is `us-west-2` and `modelArn` is the Amazon Rerank 1.0 ARN.
- D4: `db.<coll>.listSearchIndexes()` after seed shows two indexes, both `status: READY`.
- D5: documented spec step in `docs/specs/rag-reembed.md` (to be written when the first dim/model swap is scheduled).
- D6: no Redis or app-cache code in `services/ai-orchestrator/` for Phase 1; ADR-0009 observability dashboard reports retrieval p50/p95 latency so Phase 1.5 has data to decide on cache addition.
