# ADR 0006 — RAG chunking + per-query retrieval pattern

Date: 2026-06-01
Status: Proposed (Phase B of retrieval-system planning)
Decision-makers: FDE pair (delivery lead + author)
Phase: 1 — AI Adoption · Milestone M2 (Grounded Retrieval)
Related: ADR-0005 (foundation stack) · PRD §6 REQ-RAG-1..4

## Context

ADR-0005 locked the foundation: `amazon.titan-embed-text-v2:0` @ 512 dims on `mongodb/mongodb-atlas-local:8.0.8` with `langchain-mongodb`'s `MongoDBAtlasHybridSearchRetriever`. This ADR settles the two remaining design choices that drive index shape and query behavior: **how the FAR corpus is chunked** and **how the retriever decides per-query whether to favor dense or sparse signal**.

## Decisions

### D1 — Two-stage splitter: MarkdownHeaderTextSplitter → RecursiveCharacterTextSplitter

Stage 1 splits on FAR structural headers, Stage 2 splits any chunk still over budget. Source: https://docs.langchain.com/oss/python/integrations/splitters — RecursiveCharacterTextSplitter is the v1 "recommended starting point" because it "keeps larger units (e.g., paragraphs) intact"; MarkdownHeaderTextSplitter "preserves the logical organization of the document." Combined with AWS Titan guidance (https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html), quoted: *"for retrieval tasks, it is recommended to segment documents into logical segments, such as paragraphs or sections."*

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#",   "far_part"),       # Part I, II, III, IV
        ("##",  "far_section"),    # Sections A through M (per ADR-0005 D4)
        ("###", "far_subsection"), # L.1, L.2, M.3, etc.
    ]
)

char_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1200,
    chunk_overlap=150,
    separators=["\n\n", "\n", ". ", " "],
)
```

**Chunk-size rationale (1200 chars / ~800-1000 tokens):**
- Well under Titan v2's 8192-token window — embedder operates in its high-confidence range.
- Large enough to keep a typical FAR subsection (L.5, M.2) intact; small enough that section-internal granularity is preserved for citation precision.
- 150-char overlap (~10-12%) preserves cross-paragraph context without bloating index size.

**Why not a semantic splitter** (embedding-distance-based boundaries): doubles seed-ingest cost (one embed call per *candidate* boundary in addition to the final per-chunk embed). Hairpin budget rules it out for Phase 1. Captured as an escalation lever if section-header splits prove too coarse during eval.

### D2 — Chunk document schema (what we store)

```python
{
    "_id":           ObjectId(),
    "tenant_id":     "agency-xyz",           # REQ-RAG-3 isolation; filter field on indexes
    "text":          "<chunk text>",
    "embedding":     [...],                   # 512 floats (Titan v2 @ 512 per ADR-0005 D2)
    "far_part":      "IV",                    # I | II | III | IV (per ADR-0005 D4)
    "far_section":   "L",                     # A through M; filter field
    "far_subsection":"L.5",                   # nullable
    "far_clause":    "52.212-4",              # nullable; filter field (Part 52 clauses)
    "subpart":       "15.204-5",              # nullable
    "title":         "Instructions to Offerors",
    "source_doc":    "FAR-2026-06-01-snapshot",
    "snapshot_date": ISODate("2026-06-01"),
    "chunk_index":   0,
    "char_start":    0,
    "char_end":      1187,
}
```

Filter fields declared on the vectorSearch index (per https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-type/): `tenant_id`, `far_section`, `far_clause`. Pre-filter happens **before** the ANN scan — enforces multi-tenant isolation at the index level (not post-hoc), and lets section-scoped queries (e.g., "search only Section M") skip irrelevant vectors entirely.

Citation fields (`far_part`, `far_section`, `far_subsection`, `far_clause`, `subpart`, `source_doc`, `snapshot_date`) are the audit-replay payload that ADR-0008 will require for OIG-defensible grounding.

### D3 — Query-shape classification drives per-query RRF weights

A cheap regex/keyword classifier at request entry sets `vector_weight` and `fulltext_weight` on `MongoDBAtlasHybridSearchRetriever` (params confirmed on https://reference.langchain.com/python/langchain-mongodb/retrievers/MongoDBAtlasHybridSearchRetriever — defaults 1.0 / 1.0, RRF penalties default 60 / 60).

| Trigger | vector_weight | fulltext_weight | Rationale |
|---|---|---|---|
| Regex match `\d{2}\.\d{3}(-\d+)?` (FAR clause number) | 0.5 | 2.0 | BM25 lexical match nails clause IDs; embeddings dilute short literal tokens. |
| Known-acronym hit (SBSA, IDIQ, LPTA, FBO, …) | 0.5 | 2.0 | Same reasoning — short literals lose in vector space. |
| Free-text semantic phrase (no clause/acronym, length > 8 words) | 1.5 | 0.7 | Paraphrase-resistant intent; BM25 misses synonyms. |
| Default | 1.0 | 1.0 | Balanced RRF. |

**Why pre-classify instead of "let the agent pick which retriever":** Two-tool-and-LLM-decides costs an extra LLM hop per query (Sonnet 4.5 call ~$3/1M input tokens). A regex sniffer is microseconds and free. The agentic path is a Phase-1.5 escalation if classification ever miscategorizes enough to move eval numbers.

**Hybrid as the always-on default** because MongoDB's hybrid-search docs explicitly recommend it for the FAR shape: *"Particularly useful when datasets contain proper nouns or specific keywords that may not be well-represented in embedding model training."* (https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/vector-search-with-full-text-search/) FAR is exactly that — proper nouns (agency names), specific keywords (clause IDs), and semantic prose interleaved.

### D4 — Tenant pre-filter is mandatory on every retrieval call

```python
retriever = MongoDBAtlasHybridSearchRetriever(
    vectorstore=vector_store,
    search_index_name="far_search_idx",
    k=20,                                    # candidate pool size (rerank narrows in ADR-0007)
    vector_weight=v_w,                       # set per-query by classifier
    fulltext_weight=f_w,
    pre_filter={"tenant_id": tenant_id},     # MANDATORY; enforces REQ-RAG-3
)
```

`tenant_id` is asserted-by-caller but **must** be enforced at the retriever boundary — never trust the agent to pass it. Wiring + test proof of cross-tenant isolation deferred to ADR-0008.

### D5 — `$rankFusion` Preview-status flag

MongoDB docs label `$rankFusion` and `$scoreFusion` as **Preview** features. Source: https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/vector-search-with-full-text-search/. Acceptable for Phase 1 dev + eval on `atlas-local`; before any Phase 1.5 promotion to cloud Atlas prod, re-verify GA status. If still Preview at promotion time, options are: (a) switch to manual fusion via `$unionWith` (custom code — guideline-6 violation, requires approval), (b) delay rollout until GA, (c) accept Preview SLA. Decision deferred until the situation is real.

## Consequences

**Positive:**
- Section identity preserved in metadata → citations can resolve to FAR Part/Section/Subsection/Clause precisely, satisfying PRD "grounded or withheld" + "auditable by default".
- Pre-filter on index = tenant isolation enforced before scoring (cheaper than post-filter, and a structural defense against the multi-tenant leak failure mode REQ-RAG-3 names).
- Cheap regex classifier captures the lion's share of FAR query shapes without an LLM-routing tax.
- All fusion math handled by `langchain-mongodb` — zero homegrown code (guideline-6 honored).

**Negative / tradeoffs:**
- Markdown-header splitter assumes the FAR corpus snapshot in `docs/reference/far/` is already structured as markdown with `#`/`##`/`###` boundaries. Snapshot loader (D5 in ADR-0005) takes on the job of turning acquisition.gov HTML/XML into that shape. Loader code is in scope for the M2 ticket.
- Classifier is rule-based; novel query shapes get the balanced default and may underperform on edge cases. Phase D eval catches this.
- `$rankFusion` Preview status is a real risk for prod promotion (D5). Captured, not closed.

## Verification

- D1/D2: a snapshot of FAR Part 15.2 ingests into Atlas with the schema above; spot-checks confirm `far_section` populated correctly for L, M, K chunks.
- D3: `pytest tests/test_retrieval_classifier.py` has cases for `"FAR 52.212-4"`, `"IDIQ ceiling"`, `"how should past performance weight against price"`, and a default phrase — assert weight tuple per the table.
- D4: integration test where tenant-A retrieval cannot surface a tenant-B-tagged chunk (proof deferred to ADR-0008 wiring, but the `pre_filter` argument is non-optional in the retriever factory function).
- D5: a CI check or runbook note flags Preview status — re-check before any prod move.
