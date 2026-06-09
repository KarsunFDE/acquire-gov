# M2 Retrieval Pipeline — Implementation Spec

**Phase 1 · Milestone M2** · Consolidates ADR-0005..0011 into one implementer-grade document. No new decisions; every claim cites the locking ADR section.

## 1. Purpose

Implementer entry point for building Slice C of [`docs/specs/m2-rollout.md`](./m2-rollout.md). This spec consolidates the M2 ADR catalog (ADR-0005..0011) into endpoint contracts, stage-by-stage data flow, module layout, and configuration so a sub-agent can implement C1..C11 without re-opening any ADR. Quality/eval, corpus content, and UI live in sibling specs (see §13).

Relationship to `m2-rollout.md`: the rollout spec owns **PR ordering, branch strategy, CI gates, label workflow**. This spec owns **what each PR builds**.

## 2. Pipeline diagram

```
Angular SPA / Admin UI
    │  POST /draft-solicitation/section | POST /ingest/document | POST /retrieve
    │  Headers: X-Tenant-ID, X-Request-ID
    ↓
Spring Cloud Gateway :8080
    │  /ai/*       → ai-orchestrator
    │  /ingest/*   → ai-orchestrator
    ↓
ai-orchestrator FastAPI :8000
    │
    ├─ slowapi rate-limit (per X-Tenant-ID; 30/min, 1000/day)   [ADR-0011 D4]
    ├─ QueryGuardrails.evaluate                                 [ADR-0011 D2]
    ├─ build_far_retriever(tenant_id=...)                       [ADR-0008 D2]
    │      ↓ MongoDBAtlasHybridSearchRetriever.invoke           [ADR-0006 D3, D4]
    │      ↓ Mongo atlas-local 8.0.8 ($rankFusion)              [ADR-0005 D3]
    │      → 20 candidates
    ├─ rerank_and_gate(query, candidates)                       [ADR-0007 D3]
    │      ↓ boto3 bedrock-agent-runtime us-west-2 Rerank 1.0   [ADR-0005 D2]
    │      → ("pass"|"hitl"|"withhold", top-5)
    ├─ (draft path only) ChatBedrockConverse + delimiter wrap   [ADR-0003, ADR-0011 D1.2]
    │      ↓ Bedrock claude-sonnet-4-5 (us.anthropic...)
    ├─ verify_citations                                         [ADR-0011 D3]
    └─ audit_log.insert (auditLogWriter role)                   [ADR-0008 D3]
```

## 3. Stage-by-stage contract

One row per pipeline stage. Failure column covers every row of ADR-0009 D4.

| # | Stage | Input | Output | Failure → behavior → `audit_log.outcome` | ADR |
|---|---|---|---|---|---|
| 1 | Rate-limit | `X-Tenant-ID` header | Pass-through or 429 | Over-limit → 429 `rate_limited`; no audit (slowapi short-circuits before handler) | ADR-0011 D4 |
| 2 | Query guardrail (`QueryGuardrails.evaluate`) | `query: str`, `tenant_id` | `GuardrailDecision(action="pass"\|"reject", reason)` | Reject → 403 `query_blocked` (reason ∈ jailbreak_pattern\|query_too_long\|off_topic); audit `action: "query_blocked"`, query hashed | ADR-0011 D2 |
| 3 | Retriever factory (`build_far_retriever`) | kw-only `tenant_id`, weights | `MongoDBAtlasHybridSearchRetriever` instance | Missing tenant_id → `TypeError` at construct; cannot reach this stage without it | ADR-0008 D2 |
| 4 | Query classifier | `query: str` | `(vector_weight, fulltext_weight)` | No-match → default `(1.0, 1.0)`; never raises | ADR-0006 D3 |
| 5 | Query embed (Titan v2 @ 512) | `query: str` | `list[float]` len 512 | Bedrock 5xx → tenacity retry; exhaustion → 503 `bedrock_unavailable`; audit outcome `embed_failed` | ADR-0005 D2, ADR-0009 D4 |
| 6 | Hybrid retrieval (`$rankFusion`) | embedding + query + `pre_filter={"tenant_id"}` | up to 20 candidate docs | Mongo down or index `status != READY` → 503 `mongo_unavailable`; audit `retrieval_failed`. `$rankFusion` fusion failure → fall back to vector-only (`fulltext_weight=0`), set `degraded_mode=true`; audit `degraded_vector_only` | ADR-0006 D3-D4, ADR-0009 D4 |
| 7 | Rerank (`rerank_and_gate`) | query + 20 candidates | `(decision, top-5)` where decision ∈ pass\|hitl\|withhold | Bedrock 5xx → tenacity retry; exhaustion → top-5 by raw hybrid score, force `requires_human_review=true`, `gate_decision="rerank_unavailable_passthrough"`; audit `rerank_unavailable_hitl` | ADR-0007 D2-D3, ADR-0009 D4 |
| 8 | Threshold gate | `top_score: float` | `pass` if ≥0.5, `hitl` if 0.3≤s<0.5, `withhold` if <0.3 | `withhold` → empty citations, audit `withheld`. `hitl` → return citations + flag, audit `hitl_pending`. Top score absent (empty candidates) → withhold | ADR-0007 D2, ADR-0009 D4 |
| 9 | Delimiter wrap (draft path only) | top-5 chunks | prompt with `<retrieved_context type="far_data" trust_level="reference_only">` wrappers | n/a (pure transform) | ADR-0011 D1.2 |
| 10 | Generation (Sonnet 4.5; draft path only) | wrapped prompt | completion + citations array | Bedrock 5xx → tenacity retry; exhaustion → 503 `bedrock_unavailable`; audit `generation_failed` | ADR-0003, ADR-0009 D4 |
| 11 | Citation verify (`verify_citations`) | completion + retrieved top-5 | bool or raises `CitationVerificationFailed` | Unknown chunk_id in completion → 422 `citation_verification_failed`; audit outcome same; unknown IDs preserved in record | ADR-0011 D3 |
| 12 | Audit insert | full record per §8 schema | `_id` of inserted doc | Mongo write failure → 503 `mongo_unavailable`; response NOT returned until insert acknowledged (sync write-through) | ADR-0008 D3 |

## 4. Locked endpoint contracts

These contracts are the canonical shapes other M2 specs consume (UI, eval, corpus). Do not modify in implementation without an ADR.

### 4.1 `POST /retrieve`

```
Headers:
  X-Tenant-ID: <str>   (required; missing → 400 tenant_id_required)
  X-Request-ID: <uuid> (optional; orchestrator generates if absent)

Body (application/json):
  {
    "query": str (1-2000 chars; enforced via Pydantic strict),
    "far_section_filter": list[str] (optional; max 12; values from A-M enum),
    "k": int (optional; clamped to <=20; >20 → 422 k_exceeded)
  }

Response 200 pass:
  {
    "outcome": "retrieved",
    "gate_decision": "pass",
    "rerank_top_score": float,
    "citations": [
      {"chunk_id": str, "text": str, "far_part": str, "far_section": str,
       "far_subsection": str|null, "far_clause": str|null,
       "source_doc": str, "snapshot_date": str (ISO date),
       "relevance_score": float}
    ],  # length <= 5
    "request_id": str
  }

Response 200 hitl: above body + "requires_human_review": true,
                   "gate_decision": "hitl"

Response 200 withhold:
  {"outcome": "withheld", "reason": "insufficient_grounding",
   "gate_decision": "withhold", "rerank_top_score": float, "citations": [],
   "request_id": str}

Response 200 degraded (rerank unavailable):
  outcome "retrieved",
  gate_decision "rerank_unavailable_passthrough",
  requires_human_review: true,
  citations: top-5 by raw hybrid score (no relevance_score field on items),
  request_id

Response 403: {"error": "query_blocked",
               "reason": "jailbreak_pattern"|"query_too_long"|"off_topic"}
Response 422: {"error": "k_exceeded"|"citation_verification_failed", ...}
Response 429: rate_limited (per slowapi; per-tenant key)
Response 503: {"error": "bedrock_unavailable"|"mongo_unavailable",
               "request_id": str}
```

### 4.2 `POST /draft-solicitation/section`

```
Headers: X-Tenant-ID, X-Request-ID

Body:
  {
    "section_id": "A"|"B"|"C"|"D"|"E"|"F"|"G"|"H"|"J"|"K"|"L"|"M",
    "solicitation_id": str,
    "query": str (optional; defaults to section-specific template),
    "constraints": str (optional; <=1000 chars)
  }

Internal flow:
  1. QueryGuardrails.evaluate(query, tenant_id)              (ADR-0011 D2)
  2. /retrieve internal call → top-5 chunks
  3. If withhold → return { outcome:"withheld", section_text:null, ... }
  4. Else: wrap chunks in
     <retrieved_context type="far_data" trust_level="reference_only">
     delimiters                                              (ADR-0011 D1.2)
  5. ChatBedrockConverse.invoke(prompt) — Sonnet 4.5         (ADR-0003)
  6. verify_citations(completion, retrieved)                 (ADR-0011 D3)
     fail → 422 citation_verification_failed
  7. audit_log.insert(schema_v1)                             (ADR-0008 D3)
  8. Return:
     {
       "outcome": "draft_returned"|"hitl_pending"|"withheld"
                  |"citation_verification_failed",
       "section_text": str|null,
       "section_id": str,
       "citations": [...],
       "gate_decision": "pass"|"hitl"|"withhold"
                        |"rerank_unavailable_passthrough",
       "requires_human_review": bool,
       "rerank_top_score": float|null,
       "request_id": str
     }
```

### 4.3 `POST /ingest/document`

Shape locked here for cross-spec consistency. Full ingest pipeline (parsers, batching, dedup) belongs to `m2-synthetic-corpus.md`.

```
Headers: X-Tenant-ID, X-Request-ID
  Admin role required — TODO: role enforcement is M1 territory; mark open (§13)

Form data:
  file: bytes (<=10MB; >10MB → 413)
  metadata: JSON string {
    "source_doc_name",
    "far_part"?, "far_section"?,
    "snapshot_date" (ISO),
    "doc_class": "far_reference"|"synthetic_solicitation"|"agency_template"
  }
  format: "md"|"txt"|"pdf"|"json-prechunked"

Response 200:
  {"document_id": str, "chunks_inserted": int,
   "flagged_chunks": [], "duration_ms": int}

Response 422:
  {"error": "chunk_quality_flag_raised",
   "flagged_chunk_ids": [...]}                              (ADR-0011 D1.1)
  Human review required before ingest commits.

Response 413: payload_too_large
```

### 4.4 `GET /audit-log`

```
Query: tenant_id (required), request_id?, from_ts?, to_ts?, action?
Response: list of audit_log v1 records (§8 schema).

Auth: auditLogReader DB role.
Orchestrator service user binds to auditLogWriter ONLY — this endpoint is
NOT served by the orchestrator. OIG-replay endpoint owner TBD; see §13.
```

## 5. Module layout

`services/ai-orchestrator/app/` file structure. Existing `legacy_chain.py` modernizes in Slice A PR A1 (per `m2-rollout.md`) and remains until then.

| Path | Owns | Source ADRs |
|---|---|---|
| `config.py` | Every constant in §10 table; env-var override path | ADR-0010 D3 |
| `bedrock_client.py` | Embed (Titan v2 @ 512), Chat (Sonnet 4.5), Rerank (Amazon Rerank 1.0 @ us-west-2), Judge (Nova Micro — eval-only) clients; single bearer-token auth | ADR-0005 D2, ADR-0007 D3, ADR-0009 D2 |
| `retrieval.py` | `build_far_retriever(*, tenant_id, vector_weight, fulltext_weight)` factory + regex/keyword query classifier per ADR-0006 D3 table | ADR-0006 D3-D4, ADR-0008 D2 |
| `rerank.py` | `rerank_and_gate(query, candidates, withhold_threshold, hitl_threshold) -> (Literal["pass","hitl","withhold"], list[dict])`; reference impl per ADR-0007 D3 | ADR-0007 D1-D3 |
| `guardrails.py` | `QueryGuardrails.evaluate(query, tenant_id) -> GuardrailDecision`; regex layer + Nova Micro LLM-as-judge for borderline | ADR-0011 D2 |
| `citations.py` | `verify_citations(generation_result, retrieved_chunks) -> bool`; raises `CitationVerificationFailed(unknown_ids=[...])` | ADR-0011 D3 |
| `audit.py` | Append-only writer bound to `auditLogWriter` role; schema-v1 record builder; sync write-through before response return | ADR-0008 D3 |
| `prompts/retrieval_prompt.py` | System prompt with "data not instructions" directive + `<retrieved_context type="far_data" trust_level="reference_only">` wrapper template | ADR-0011 D1.2 |
| `api/retrieve.py` | `POST /retrieve` router | ADR-0007 D2, ADR-0011 D4 |
| `api/draft.py` | `POST /draft-solicitation/section` router | ADR-0003, ADR-0008 D3 |
| `api/ingest.py` | `POST /ingest/document` router (call sequence only; parsers in corpus spec) | ADR-0011 D1.1 |
| `seed/` | Index DDL runner, FAR snapshot ingestor (content delegated to corpus spec) | ADR-0007 D4, ADR-0010 D5 |
| `legacy_chain.py` | Pre-v1 `LLMChain.run` — present until Slice A PR A1 modernizes it | brownfield Item 5 |

Tool-argument Pydantic schemas (ADR-0011 D5) live alongside the agent tools they validate; not in `api/`. Wiring deferred to M2-10 / M2-17 (§12).

## 6. Inter-service call shapes

Phase 1 M2: gateway is a dumb pass-through on `/ai/*` and `/ingest/*`. The orchestrator owns all retrieval, gate, audit, and rate-limit logic.

| Hop | Forwards | Adds | Notes |
|---|---|---|---|
| SPA → Gateway | request body + `X-Tenant-ID`, `X-Request-ID` if present | nothing | Caller is expected to set both headers; gateway is not configured to inject either |
| Gateway → orchestrator | request body + headers verbatim | nothing | brownfield Item 6 (no correlation-id logging in gateway) **stays deliberate**; gateway does NOT inject `X-Request-ID`. Orchestrator generates a UUID if absent. Known seam, scheduled fix is Phase 2. |
| orchestrator → Bedrock | per `bedrock_client.py` per-service; single `AWS_BEARER_TOKEN_BEDROCK` | tenacity retry envelope (ADR-0004 B1) | Rerank pins region us-west-2; chat/embed/judge inherit AWS_REGION |
| orchestrator → Mongo | per `retrieval.py` / `audit.py` | tenant pre-filter on every `$vectorSearch`; auditLogWriter role on every audit insert | Single MongoClient instance; `?directConnection=true` mandatory (ADR-0005 D3) |
| orchestrator → solicitation-service | none in M2 | n/a | Cross-service call is M3 territory |

## 7. Tenant isolation enforcement — three layers

Pasted from ADR-0008 D2 with module-layout mapping added.

| Layer | Mechanism | Location | ADR |
|---|---|---|---|
| Structural | `$vectorSearch.filter` pre-filter on `tenant_id` runs **before** ANN scan; filter declared on `far_vector_idx` per ADR-0007 D4 | Mongo index DDL — `seed/` runs `db.chunks.createSearchIndex(...)` | ADR-0008 D2, ADR-0007 D4 |
| Factory | `build_far_retriever(*, tenant_id: str, ...)` — `tenant_id` is **keyword-only required**; no default; no positional fallback. Direct construction of `MongoDBAtlasHybridSearchRetriever` outside this factory is review-blocking | `retrieval.py` | ADR-0008 D2 |
| CI gate | `pytest -m req_rag_3` runs on every PR; must stay **green** (inverse of brownfield-debt locked-failing). Tests: same-content seed across two tenants (ADR-0008 D2), plus three adversarial-query cases (ADR-0011 D6: jailbreak text, section-filter escalation, embedded `tenant_id=` in query) | `services/ai-orchestrator/tests/test_cross_tenant_retrieval_impossible.py`; runner in `.github/workflows/` | ADR-0008 D2, ADR-0011 D6 |

Removing or weakening any single layer requires the same approval flow as a brownfield-debt touch (debt-touch-approved-equivalent label, ADR).

## 8. Audit-log v1 schema

Pasted from ADR-0008 D3 verbatim. Schema version is `1` from day one; future evolution is additive only (append-only DB role enforces this at the resource level).

```python
{
    "_id":           ObjectId(),
    "ts":            ISODate("..."),
    "tenant_id":     "agency-xyz",                     # REQ-RAG-3 required
    "request_id":    "<correlation id>",                # trace across services
    "actor":         {"user_id": "...", "role": "CO|specialist|reviewer", "session_id": "..."},
    "action":        "retrieval_and_generate",          # | retrieval_only | issue_solicitation | amend_solicitation | hitl_decision | query_blocked
    "request":       {"query": "...", "query_hash": "<sha256>"},
    "retrieval":     {
        "retriever_class":  "MongoDBAtlasHybridSearchRetriever",
        "vector_weight":    1.0,
        "fulltext_weight":  1.0,
        "candidates":       [{"chunk_id": ObjectId, "vector_score": 0.82, "fulltext_score": 0.71}, ...],
        "rerank_model":     "amazon.rerank-v1:0",
        "rerank_top":       [{"chunk_id": ObjectId, "relevance_score": 0.74}, ...],
        "gate_decision":    "pass|hitl|withhold|rerank_unavailable_passthrough",
    },
    "generation":    {
        "model":            "anthropic.claude-sonnet-4-5",
        "prompt_hash":      "<sha256>",                       # NOT raw prompt
        "completion_hash":  "<sha256>",                       # NOT raw completion
        "input_tokens":     1234,
        "output_tokens":    567,
        "citations":        [                                  # RAW, not hashed
            {"chunk_id": ObjectId(), "far_part": "IV", "far_section": "L",
             "far_clause": "52.212-4", "snapshot_date": "2026-06-01"}
        ],
    },
    "hitl":          {                                          # present only when interrupt fired
        "thread_id":        "<langgraph thread_id>",
        "interrupt_at":     "issue_solicitation",
        "approver_user_id": "...",
        "decision":         "approve|reject",
        "decision_ts":      ISODate("..."),
    },
    "outcome":       "draft_returned|withheld|hitl_pending|hitl_approved|hitl_rejected|citation_verification_failed|embed_failed|retrieval_failed|degraded_vector_only|rerank_unavailable_hitl|generation_failed|query_blocked",
    "schema_version": 1,
}
```

**Role binding.** Orchestrator service user binds to `auditLogWriter` (privileges: `insert`, `find` only — explicitly NO `update`, NO `remove`; ADR-0008 D3). Reads by OIG / CO replay go through a separate (Phase 1.5) endpoint backed by `auditLogReader` — out of scope for this spec (see §13).

**Write-through.** Audit insert is **synchronous**: the API response is not returned until the audit insert is acknowledged. ADR-0010 D6 item M2-12 — "audit-log writes happen on the path, not async."

**Indexes** (ADR-0010 D5): `{ts: 1}`, `{tenant_id: 1, ts: -1}`, `{request_id: 1}` — match the OIG-replay query patterns.

## 9. Failure modes + HTTP mapping

Restates ADR-0009 D4 table with explicit HTTP status mapping. Every failure terminates in an `audit_log.outcome` value.

| Stage | Failure | HTTP | Audit outcome | Behavior |
|---|---|---|---|---|
| Rate-limit | Over per-tenant cap | 429 | (none — slowapi pre-handler) | `rate_limited` |
| Guardrail | Reject (jailbreak\|too-long\|off-topic) | 403 | `query_blocked` | Query hash recorded; raw query NOT stored |
| Body validation | `k > 20` | 422 | (none — pre-handler) | `k_exceeded` |
| Body validation | Missing `X-Tenant-ID` | 400 | (none — pre-handler) | `tenant_id_required` |
| Query embed | Bedrock 5xx after tenacity exhaustion | 503 | `embed_failed` | `bedrock_unavailable` |
| Retrieval | Mongo down or index `status != READY` | 503 | `retrieval_failed` | `mongo_unavailable` |
| Hybrid fusion | `$rankFusion` Preview failure | 200 | `degraded_vector_only` | Vector-only fallback; `degraded_mode=true` in response |
| Rerank | Bedrock 5xx after tenacity exhaustion | 200 | `rerank_unavailable_hitl` | Top-5 by raw hybrid score; `requires_human_review=true` forced; `gate_decision="rerank_unavailable_passthrough"` |
| Threshold gate | Top score < 0.3 | 200 | `withheld` | Empty citations; `outcome="withheld"`, `reason="insufficient_grounding"` |
| Threshold gate | 0.3 ≤ top score < 0.5 | 200 | `hitl_pending` | Citations + `requires_human_review=true` |
| Threshold gate | Top score ≥ 0.5 | 200 | `draft_returned` (draft path) / `retrieved` (retrieve-only) | Pass |
| Generation (draft) | Bedrock 5xx after tenacity exhaustion | 503 | `generation_failed` | `bedrock_unavailable` |
| Citation verify (draft) | Unknown chunk_id in completion | 422 | `citation_verification_failed` | Unknown IDs preserved in audit record |
| Audit insert | Mongo write failure | 503 | (none — response NOT returned) | `mongo_unavailable`; client must retry |
| Ingest | Chunk quality flag raised | 422 | `ingest_blocked` | Human review required; chunks NOT persisted |
| Ingest | File > 10MB | 413 | (none — pre-handler) | `payload_too_large` |

**No circuit breaker** on Bedrock client — brownfield Item 3, scheduled W4 cohort work (CLAUDE.md). Tenacity full-jitter retry + explicit 5xx mapping is the Phase 1 contract (ADR-0004 B1, ADR-0009 D4).

## 10. Configuration — source of truth

Every config knob lives in `services/ai-orchestrator/app/config.py`. Env vars override at process start. **Load order: defaults → env vars** — no per-request overrides except where explicitly allowed (per-query RRF weights set by the classifier in `retrieval.py`).

Pasted from ADR-0010 D3.

| Constant | Default | Source | Notes |
|---|---|---|---|
| `BEDROCK_GEN_MODEL` | `us.anthropic.claude-sonnet-4-5-...` | ADR-0003 | generator model |
| `BEDROCK_EMBED_MODEL` | `amazon.titan-embed-text-v2:0` | ADR-0005 D2 | embedder |
| `BEDROCK_EMBED_DIMS` | `512` | ADR-0005 D2 | quality-cost lever |
| `BEDROCK_RERANK_MODEL_ARN` | `arn:aws:bedrock:us-west-2::foundation-model/amazon.rerank-v1:0` | ADR-0005 D2, ADR-0007 D3 | hardcoded region |
| `BEDROCK_RERANK_REGION` | `us-west-2` | ADR-0005 D2 | NOT us-east-1 |
| `BEDROCK_JUDGE_MODEL` | `amazon.nova-micro-v1:0` | ADR-0009 D2 | eval-side only |
| `MONGO_URI` | `mongodb://user:pass@mongodb:27017/?directConnection=true` | ADR-0005 D3 | atlas-local requires directConnection |
| `MONGO_DB` | `acquire_gov` | ADR-0008 D5 | single DB; tenants filter-scoped |
| `CHUNKS_COLLECTION` | `chunks` | ADR-0008 D5 | RAG corpus |
| `AUDIT_LOG_COLLECTION` | `audit_log` | ADR-0008 D3 | append-only via role |
| `VECTOR_INDEX_NAME` | `far_vector_idx` | ADR-0007 D4 | vectorSearch index |
| `SEARCH_INDEX_NAME` | `far_search_idx` | ADR-0007 D4 | $search (BM25) index |
| `RETRIEVAL_K_CANDIDATES` | `20` | ADR-0007 D2 | hybrid top-k before rerank |
| `RERANK_TOP_N` | `5` | ADR-0007 D2 | post-rerank final count |
| `RERANK_WITHHOLD_THRESHOLD` | `0.3` | ADR-0007 D2 | top score below → withhold |
| `RERANK_HITL_THRESHOLD` | `0.5` | ADR-0007 D2 | top score below → HITL flag |
| `RAGAS_THRESHOLD_FAITHFULNESS` | `0.85` | ADR-0009 D1 | one-way ratchet floor |
| `RAGAS_THRESHOLD_ANSWER_RELEVANCY` | `0.80` | ADR-0009 D1 | one-way ratchet floor |
| `RAGAS_THRESHOLD_CONTEXT_PRECISION` | `0.75` | ADR-0009 D1 | one-way ratchet floor |
| `RAGAS_THRESHOLD_CONTEXT_RECALL` | `0.80` | ADR-0009 D1 | one-way ratchet floor |
| `CHUNK_SIZE` | `1200` | ADR-0006 D1 | char target |
| `CHUNK_OVERLAP` | `150` | ADR-0006 D1 | char overlap |
| `MAX_QUERY_CHARS` | `2000` | ADR-0011 D2, D4 | DoS guard + Guardrail signal |
| `MAX_RESPONSE_CHARS` | `8000` | ADR-0011 D4 | response body cap |
| `VECTOR_SEARCH_NUM_CANDIDATES` | `100` | ADR-0011 D4 | $vectorSearch knob |
| `RATE_LIMIT_QUERIES_PER_MINUTE_PER_TENANT` | `30` | ADR-0011 D4 | conservative start |
| `RATE_LIMIT_QUERIES_PER_DAY_PER_TENANT` | `1000` | ADR-0011 D4 | hairpin-budget alignment |

**Env vars** (from `.env` / docker-compose):

| Env var | Notes | Source |
|---|---|---|
| `AWS_BEARER_TOKEN_BEDROCK` | Bedrock API-key auth; same path for chat + embed + rerank + judge | ADR-0005 D2 |
| `AWS_REGION` | default for chat client; rerank overrides to us-west-2 | ADR-0007 D3 |
| `BEDROCK_RERANK_REGION` | NOT us-east-1 | ADR-0005 D2 |
| `LANGSMITH_TRACING` | **NEVER set to `true`** in Phase 1 | ADR-0009 D3 |

`BEDROCK_MODEL_ID` three-source drift (CLAUDE.md known issue) is **not** consolidated here — that's W2 cohort modernization. `BEDROCK_GEN_MODEL` is the new M2 source of truth for the generator; the legacy drift stays put until cohort week (ADR-0010 D3 note).

## 11. Bedrock client region pinning

| Client | Service | Region | Why |
|---|---|---|---|
| Chat (Sonnet 4.5) | `bedrock-runtime` | Inherited from `AWS_REGION`; cross-region inference profile `us.anthropic.claude-sonnet-4-5-...` routes through us-west-2 transparently | ADR-0003 pilot pattern |
| Embed (Titan v2 @ 512) | `bedrock-runtime` | Inherited from `AWS_REGION` | ADR-0005 D2 |
| Rerank (Amazon Rerank 1.0) | `bedrock-agent-runtime` | **HARD-PINNED `us-west-2`** | Not available in us-east-1 per AWS docs (ADR-0005 D2) — only Bedrock service in orchestrator that pins region |
| Judge (Nova Micro) | `bedrock-runtime` | Inherited from `AWS_REGION` | Eval-only — see `m2-eval-harness.md` |

The region split is the one infrastructure knob operators can misconfigure. `BEDROCK_RERANK_REGION` env var surfaces it.

## 12. What's stubbed in Phase 1, what's real

| Capability | Status in initial-retrieval Slice C | Source |
|---|---|---|
| `/retrieve` endpoint | **Real** — C9 lands the full pipeline | `m2-rollout.md` C9 |
| `/draft-solicitation/section` endpoint | **Real** — wraps retrieve + generate + verify + audit | this spec §4.2 |
| `/ingest/document` endpoint | **Real** (call shape); content parsers in corpus spec | this spec §4.3 |
| Retrieval (hybrid + tenant filter) | **Real** — C4, C5 | ADR-0006, ADR-0008 D2 |
| Rerank + threshold gate | **Real** — C6 | ADR-0007 D2-D3 |
| Embeddings (Titan v2) | **Real** — C3 | ADR-0005 D2 |
| Query guardrails | **Real** — C8 | ADR-0011 D2 |
| Citation verify | **Real** — C7 | ADR-0011 D3 |
| Rate limit (slowapi, in-process) | **Real** — C9 | ADR-0011 D4 |
| Audit log v1 + roles | **Real** — C7 | ADR-0008 D3 |
| Agent loop (`create_agent`) | **Stubbed in Phase 1 initial-retrieval** — arrives with M2-10 (deferred per `m2-rollout.md`) | ADR-0008 D4 |
| HITL middleware (`HumanInTheLoopMiddleware`) | **Stubbed** — arrives with M2-10 (deferred); needs `issue_solicitation`/`amend_solicitation` tools to exist first | ADR-0008 D4, `m2-rollout.md` Deferred table |
| MongoDBSaver checkpointer | **Stubbed** — arrives with M2-10/M2-11 (deferred) | ADR-0008 D5 |
| Tool-arg Pydantic strict | **Stubbed** — arrives with M2-10/M2-17 (deferred); only needed when agent path exists | ADR-0011 D5 |

The /retrieve and /draft-solicitation/section endpoints in Slice C are **direct retriever-invoke + Bedrock-invoke**, not agent-wrapped. M2-10/11/17 add the agent layer once M3 work begins.

## 13. Open items / not-decided

- **OIG-replay endpoint owner.** `GET /audit-log` is NOT served by the orchestrator (service user binds to `auditLogWriter` only, no read role). Endpoint owner + admin-role enforcement TBD. ADR-0008 D3 notes the read role exists; specifying *where* the read endpoint lives is outside this spec. Likely solicitation-service or a new admin-service; flag for Phase 1.5 planning.
- **Admin-role enforcement on `/ingest/document`.** ADR-0011 D4 specifies rate limit + size cap; role-based auth on the ingest endpoint is M1 territory (pilot ADR-0003 / ADR-0004) and not closed here. Mark as a known seam; default Phase 1 behavior is "tenant header trusted, admin role not enforced."
- **Corpus lean-scope caveat.** Phase 1 corpus is ~10 synthetic solicitations × 2 agencies × **FAR Parts I + II only**. Sections L/M drafting will surface lower rerank confidence until Phase 1.5 expands corpus to Parts III/IV. The wizard still allows AI-draft on L/M but expect more `hitl` / `withhold` outcomes than on C/H. Eval harness threshold-ratchet (ADR-0009 D1) will reflect this baseline.

No other items in this spec's scope are unresolved.

## 14. Things this spec does NOT add

Explicit scope-out — confirms PRD §4 alignment.

- NOT: OTel / OpenTelemetry / AIOps — Phase 2 (PRD §4, ADR-0009 D3).
- NOT: Circuit breaker on Bedrock client — brownfield Item 3, W4 cohort work (CLAUDE.md, ADR-0009 D4).
- NOT: Host-disk encryption prereq (BitLocker / FileVault / LUKS) — Phase 2 (PRD §4, ADR-0008 D1).
- NOT: Tenant registry collection — Phase 2 (PRD §4, ADR-0008 D5).
- NOT: Output-side Guardrails (LLM completion filtering) — Phase 1.5 (ADR-0011 D2).
- NOT: Redis-backed slowapi for production rate limit — Phase 1.5 (ADR-0011 D4).
- NOT: App-side retrieval cache — Phase 1.5 (ADR-0007 D6).
- NOT: LangSmith (SaaS or self-hosted) — never on (ADR-0009 D3).
- NOT: Bedrock model invocation logging — never on (ADR-0009 D3).
- NOT: Output-side PII redaction — Phase 1.5 (ADR-0011 D8; Phase 1 synthetic-only).
- NOT: Eval harness — sibling spec `m2-eval-harness.md`.
- NOT: Synthetic corpus content + ingest format parsers — sibling spec `m2-synthetic-corpus.md`.
- NOT: Frontend wizard / provenance UI — sibling spec `m2-ui-far-sections.md`.
- NOT: PR ordering, branching, CI gates — already owned by `docs/specs/m2-rollout.md`.
- NOT: M3 (agent + HITL wiring beyond stubs noted in §12).

## 15. When to update this spec

- **Before C-ticket implementation starts**: if any locked endpoint contract in §4 needs adjustment, raise an ADR. Do NOT edit the contract here without one.
- **As Slice C PRs merge**: tick the §12 status table from "Real" to "Shipped"; record any contract deviation that landed in code.
- **If §13 open items resolve**: move the resolution into the relevant section and remove from §13.
- **If a new failure mode is discovered during implementation**: extend §9 with the HTTP mapping + audit outcome; raise an ADR if behavior is novel.
