# ADR 0010 — Phase 1 M2 implementation manifest (consolidated reference)

Date: 2026-06-01
Status: Proposed (Phase E of retrieval-system planning — implementation reference)
Decision-makers: FDE pair (delivery lead + author)
Phase: 1 — AI Adoption · Milestone M2 (Grounded Retrieval) — implementation bridge
Related: ADR-0005..0009 — this ADR cites no new decisions; it consolidates everything those five locked

## Purpose

ADRs 0005-0009 settled the design space. This ADR is the **single page an implementer opens** to find every dependency pin, every import path, every config knob, every env var, every CI artifact, and the ticket-ready M2 work breakdown. No new decisions live here — every line cites the ADR that locked it.

Read this before writing any M2 code.

## D1 — pip dependencies (`services/ai-orchestrator/requirements.txt` deltas)

**Current state** (from existing `requirements.txt`):
- `langchain==0.3.7`, `langchain-core==0.3.15`, `langchain-aws==0.2.7` — **PRE-v1.0** (v1 is `langchain>=1.0`).
- `pymongo==4.10.1` — OK but `langchain-mongodb` adds the wrapper layer.
- `pinecone-client==5.0.1` — brownfield Item 7, dead import; removal scheduled W2.
- `boto3==1.39.11` — bearer-token floor; stays.
- `tenacity==9.0.0` — stays per ADR-0004.

**M2 deltas (add + bump):**

| Package | Pin | Why | Cite |
|---|---|---|---|
| `langchain` | `>=1.0,<2` | Core v1 — agents, tools, chat_models, embeddings | ADR-0005 D1 |
| `langchain-aws` | `>=0.3,<1` | ChatBedrockConverse + BedrockEmbeddings | ADR-0005 D1 |
| `langchain-mongodb` | `>=0.5,<1` | MongoDBAtlasVectorSearch + MongoDBAtlasHybridSearchRetriever | ADR-0005 D1 |
| `langchain-text-splitters` | `>=0.3,<1` | MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter | ADR-0006 D1 |
| `langgraph` | `>=0.3,<1` | create_agent + HumanInTheLoopMiddleware | ADR-0008 D4 |
| `langgraph-checkpoint-mongodb` | `>=0.4,<1` | MongoDBSaver checkpointer | ADR-0008 D5 |
| `ragas` | `>=0.2,<1` | Eval framework | ADR-0009 D1 |
| `litellm` | `>=1.50,<2` | RAGAS judge LLM adapter for Bedrock | ADR-0009 D2 |
| `slowapi` | `>=0.1.9,<1` | FastAPI rate-limit decorator (per-tenant) | ADR-0011 D4 |

**Remove**: `pinecone-client` — brownfield Item 7. **Schedule per CLAUDE.md** (W2 cohort work), not eager.

**Floor versions are minimums**; resolve upper bounds at install time. Two-version pin in CI lockfile to detect breaking minor bumps.

## D2 — Import-path quick reference

```python
# Generation (chat) — ADR-0005 D1, ADR-0003 (model = us.anthropic.claude-sonnet-4-5)
from langchain_aws import ChatBedrockConverse

# Embedding — ADR-0005 D2 (model = amazon.titan-embed-text-v2:0, dims = 512)
from langchain_aws import BedrockEmbeddings

# Vector store — ADR-0005 D1, ADR-0006 D2 (collection schema)
from langchain_mongodb import MongoDBAtlasVectorSearch

# Hybrid retriever — ADR-0005 D1, ADR-0006 D3 (per-query weights)
from langchain_mongodb import MongoDBAtlasHybridSearchRetriever

# Splitters — ADR-0006 D1
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

# Agent + HITL — ADR-0008 D4
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import tool

# Checkpointer — ADR-0008 D5
from langgraph.checkpoint.mongodb import MongoDBSaver

# Rerank (NOT wrapped by langchain-aws — direct boto3) — ADR-0005 D2, ADR-0007 D3
import boto3
reranker = boto3.client("bedrock-agent-runtime", region_name="us-west-2")

# RAGAS eval — ADR-0009 D1, D2
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas.llms import llm_factory
import litellm
```

## D3 — Config knobs + env vars

`services/ai-orchestrator/app/config.py` — single source of truth:

| Constant | Default | Source | Notes |
|---|---|---|---|
| `BEDROCK_GEN_MODEL` | `us.anthropic.claude-sonnet-4-5-...` | ADR-0003 | generator model |
| `BEDROCK_EMBED_MODEL` | `amazon.titan-embed-text-v2:0` | ADR-0005 D2 | embedder |
| `BEDROCK_EMBED_DIMS` | `512` | ADR-0005 D2 | quality-cost lever |
| `BEDROCK_RERANK_MODEL_ARN` | `arn:aws:bedrock:us-west-2::foundation-model/amazon.rerank-v1:0` | ADR-0005 D2, ADR-0007 D3 | hardcoded region; bypasses chat client region |
| `BEDROCK_RERANK_REGION` | `us-west-2` | ADR-0005 D2 | NOT us-east-1 |
| `BEDROCK_JUDGE_MODEL` | `amazon.nova-micro-v1:0` | ADR-0009 D2 | eval-side only |
| `MONGO_URI` | `mongodb://user:pass@mongodb:27017/?directConnection=true` | ADR-0005 D3 | atlas-local requires directConnection |
| `MONGO_DB` | `acquire_gov` | ADR-0008 D5 | single DB; tenants are filter-scoped |
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

Note: `BEDROCK_MODEL_ID` three-source drift (CLAUDE.md known issue) — this manifest does NOT consolidate it; that's W2 cohort modernization. The `BEDROCK_GEN_MODEL` config constant is the *new* M2 source of truth for the generator; the legacy drift stays put.

## D4 — Atlas Local container changes (`infra/docker/docker-compose.yml`)

Replace the existing `mongo:latest` service. Source: ADR-0005 D3.

```yaml
services:
  mongodb:
    hostname: mongodb
    image: mongodb/mongodb-atlas-local:8.0.8       # ADR-0005 D3
    environment:
      - MONGODB_INITDB_ROOT_USERNAME=user
      - MONGODB_INITDB_ROOT_PASSWORD=pass
    ports:
      - 27019:27017
    volumes:
      - data:/data/db
      - config:/data/configdb
volumes:
  data:
  config:
```

Connection string requires `?directConnection=true`. **Reuse-the-old-volume is NOT documented as safe** — dump/restore migration per ADR-0005 D3.

## D5 — MongoDB index DDL (run at seed time)

```javascript
// ADR-0007 D4 — vector index
db.chunks.createSearchIndex({
  name: "far_vector_idx",
  type: "vectorSearch",
  definition: {
    fields: [
      { type: "vector", path: "embedding", numDimensions: 512,
        similarity: "cosine", quantization: "scalar" },
      { type: "filter", path: "tenant_id" },           // ADR-0008 D2
      { type: "filter", path: "far_section" },
      { type: "filter", path: "far_clause" }
    ]
  }
});

// ADR-0007 D4 — BM25 index
db.chunks.createSearchIndex({
  name: "far_search_idx",
  type: "search",
  definition: { mappings: { dynamic: true } }
});

// ADR-0008 D3 — audit_log role-based append-only
db.createRole({
  role: "auditLogWriter",
  privileges: [{
    resource: { db: "acquire_gov", collection: "audit_log" },
    actions: [ "insert", "find" ]
  }],
  roles: []
});
db.createRole({
  role: "auditLogReader",
  privileges: [{
    resource: { db: "acquire_gov", collection: "audit_log" },
    actions: [ "find" ]
  }],
  roles: []
});

// ADR-0008 D3 — indexes on audit_log for OIG-replay query patterns
db.audit_log.createIndex({ ts: 1 });
db.audit_log.createIndex({ tenant_id: 1, ts: -1 });
db.audit_log.createIndex({ request_id: 1 });
```

## D6 — Ticket-ready M2 work breakdown

Each item below maps to one PR-sized unit; the order respects dependencies (later items assume earlier items shipped).

**M2-01: Atlas Local container swap + connection plumbing**
- Replace `mongo:latest` with `mongodb/mongodb-atlas-local:8.0.8` in compose.
- Update `MONGO_URI` env var with `?directConnection=true`.
- mongodump existing data → bring up atlas-local empty → mongorestore.
- Verify with `db.runCommand({buildInfo:1}).version` returning `8.0.8`.
- ADR cite: 0005 D3.

**M2-02: FAR corpus snapshot ingestion**
- Download FAR Part 15.2 + Part 52 XML/HTML from acquisition.gov.
- Check into `docs/reference/far/` with MANIFEST.md + snapshot date.
- Loader script converts to markdown structure with `#`/`##`/`###` for Part/Section/Subsection.
- ADR cite: 0005 D4, D5.

**M2-03: Splitter + chunk schema implementation**
- Two-stage splitter (MarkdownHeaderTextSplitter → RecursiveCharacterTextSplitter, 1200/150).
- Per-chunk doc shape per ADR-0006 D2.
- Unit tests for each FAR section's expected chunk count + metadata.
- ADR cite: 0006 D1, D2.

**M2-04: Bedrock embedder integration**
- Add `BedrockEmbeddings` client targeting Titan v2 @ 512 dims.
- Reuses existing `AWS_BEARER_TOKEN_BEDROCK` auth.
- Seed script embeds chunks → MongoDB `chunks` collection.
- ADR cite: 0005 D2.

**M2-05: Atlas index creation**
- `createSearchIndex` for both `far_vector_idx` and `far_search_idx`.
- Run as part of seed; idempotent — skip if index exists with `status: READY`.
- ADR cite: 0007 D4.

**M2-06: Retriever factory + tenant pre-filter**
- `build_far_retriever(tenant_id, vector_weight, fulltext_weight)` — kw-only required tenant_id.
- Wraps `MongoDBAtlasHybridSearchRetriever` with `pre_filter`.
- Locked-passing pytest gate `tests/test_cross_tenant_retrieval_impossible.py` (`req_rag_3` marker).
- ADR cite: 0006 D3, D4 + 0008 D2.

**M2-07: Query classifier + per-query weight selection**
- Regex/keyword classifier per ADR-0006 D3 table.
- Unit tests covering clause-number, acronym, semantic, default cases.
- ADR cite: 0006 D3.

**M2-08: Rerank wiring + gate logic**
- `rerank_and_gate(query, candidates, ...)` per ADR-0007 D3 reference impl.
- `bedrock-agent-runtime` client pinned to us-west-2 + Amazon Rerank 1.0 ARN.
- Failure-mode handling per ADR-0009 D4 (tenacity → rerank_unavailable_hitl).
- ADR cite: 0005 D2, 0007 D1-D3, 0009 D4.

**M2-09: Append-only `audit_log` collection + roles + Bedrock-logging-disabled CI guard**
- DB roles created at seed (`auditLogWriter` / `auditLogReader`).
- Schema-version-1 record shape per ADR-0008 D3.
- Hashes for prompt + completion; raw citations.
- Service user binds to `auditLogWriter` only.
- `.github/scripts/verify-bedrock-logging-disabled.sh` asserts Bedrock model invocation logging stays OFF (one-line defensive check).
- ADR cite: 0008 D3, 0009 D3.

**M2-10: HITL middleware + checkpointer wiring**
- `MongoDBSaver` from `langgraph-checkpoint-mongodb`.
- `HumanInTheLoopMiddleware` config per ADR-0008 D4 — interrupt on `issue_solicitation`, `amend_solicitation`.
- Resume-after-multi-day test (set up checkpoint, restart container, resume).
- ADR cite: 0008 D4, D5.

**M2-11: RAGAS eval gate workflow**
- `services/ai-orchestrator/eval/far_eval_set.jsonl` — generated from FAR snapshot (NOT human-authored).
- `eval/judge.py` instantiates RAGAS with Nova Micro via LiteLLM.
- `.github/workflows/rag-eval-gate.yml` runs four metrics; ratchet against main + 2pp floor.
- ADR cite: 0009 D1, D2.

**M2-12: Endpoint integration**
- New FastAPI endpoint (per pilot ADR-0003 pattern) that exercises the full pipeline.
- Withhold + HITL + pass branches all return distinct response shapes per ADR-0007 D2.
- Audit-log writes happen on the path, not async (writeback consistency: response only after audit log insert acknowledged).
- ADR cite: 0007 D2, 0008 D3.

**M2-13: Ingest-time content scan + retrieval prompt wrapping**
- Regex `chunk_quality_flag` on ingest (indirect prompt injection — ADR-0011 D1.1).
- Retrieval prompt template wraps chunks in `<retrieved_context type="far_data" trust_level="reference_only">` delimiters with system-prompt "data not instructions" directive (ADR-0011 D1.2).
- Seed script aborts on any flagged chunk pending human review.
- ADR cite: 0011 D1.

**M2-14: Hand-built query-side Guardrails-equivalent**
- New module `app/guardrails.py` with `QueryGuardrails` class — JAILBREAK_PATTERNS regex layer + Nova Micro LLM-as-judge for borderline queries.
- All rejections write audit_log with `action: "query_blocked"` + hash-only query.
- ADR cite: 0011 D2.

**M2-15: Citation hard-fail verification**
- `verify_citations()` runs before audit_log write on every `retrieval_and_generate` outcome.
- Unknown chunk_id → 422 `citation_verification_failed` + audit record with unknown IDs preserved.
- Mocked-LLM integration test covers fabricated-id path.
- ADR cite: 0011 D3.

**M2-16: Rate limit + retrieval caps**
- Add `slowapi` dep. Per-tenant key extractor on `X-Tenant-ID` header. Decorator on /draft endpoint + /retrieve endpoint.
- Hard caps on k, numCandidates, response_chars, query_chars enforced in retriever factory + endpoint pre-validation.
- ADR cite: 0011 D4.

**M2-17: Tool-argument Pydantic strict validation**
- Every `@tool` gets a Pydantic args_schema with `strict=True, extra="forbid"`.
- Args_schema imports section enum from chunk schema module — single source of truth.
- ADR cite: 0011 D5.

**M2-18: Adversarial REQ-RAG-3 test cases**
- Extend `tests/test_cross_tenant_retrieval_impossible.py` with three adversarial cases (jailbreak query, section-scoped escalation attempt, embedded tenant_id in query).
- All keep `req_rag_3` marker; CI-blocking.
- ADR cite: 0011 D6.

**M2-19: Signed FAR snapshot manifests**
- `docs/reference/far/MANIFEST.sha256` with SHA-256 per file.
- `.github/scripts/verify-far-snapshot-manifest.sh` checks on every PR touching `docs/reference/far/`.
- GitHub label `far-snapshot-update-approved` gates legitimate manifest updates (mirrors `debt-touch-approved` pattern).
- ADR cite: 0011 D7.

**M2-20: README + .env.example update**
- Add `BEDROCK_RERANK_REGION` to `.env.example`.
- Document the synthetic-data CI guard + FAR snapshot manifest workflow.
- NO host-disk-encryption prereq (PRD §4 OOS — AI-security hardening of legacy debt = Phase 2).

**M2-21 (optional Phase 1.5 trigger)**: cloud-Atlas migration plan
- Dump from atlas-local → restore to cloud Atlas → recreate indexes.
- Encryption-at-rest gap from ADR-0008 D1 closes.
- Triggered when real-data ingest is approved.

## D7 — What this manifest does NOT include

Deliberate exclusions, captured here so a future ADR doesn't try to "fix" them outside scope:

- **App-side OTel / OpenTelemetry rollout.** PRD §4 OOS + §11 open question. Phase 2 observability ADR. ADR-0009 D3.
- **CloudWatch dashboard JSON artifact.** Auto-published metrics exist; dashboards = Phase 2 observability tooling.
- **Host-disk-encryption prereq (BitLocker / FileVault / LUKS).** AI-security hardening of legacy debt — PRD §4 OOS + CLAUDE.md. Synthetic-data constraint is the Phase-1 mitigation.
- **Tenant registry collection.** Multi-tenant rollout beyond retrieval boundary — PRD §4 OOS. tenant_id is caller-asserted per ADR-0004 M9.
- **5% human spot-check budget on judge.** Process surface PRD §4 doesn't authorize + conflicts with PRD §7 eval-as-the-gate. Drift artifacts captured structurally; review = Phase-1.5 trigger.
- **Circuit breaker on Bedrock client.** Brownfield Item 3 / W4 cohort work. CLAUDE.md.
- **`BEDROCK_MODEL_ID` three-source drift consolidation.** W2 cohort work. CLAUDE.md.
- **Item 11 — `:latest` on the other 4 Dockerfiles.** Brownfield-debt; do not pin.
- **Bedrock model invocation logging.** Explicitly off per ADR-0009 D3.
- **LangSmith (SaaS or self-hosted).** Skipped per ADR-0009 D3.
- **Postgres / Redis / SQLite checkpointer.** Replaced by MongoDBSaver per ADR-0008 D5.
- **Cohere Rerank 3.5.** Escalation lever only per ADR-0005 D2.
- **Cohere Embed v4.** Escalation lever only per ADR-0005 D2.
- **Queryable Encryption.** Phase 1.5+ if real PII enters per ADR-0008 D1.
- **App-side retrieval cache.** Phase 1.5+ post-observability per ADR-0007 D6.
- **Managed Bedrock Guardrails product.** PRD §7 "hand-built in Phase 1" — hand-built equivalent lives in ADR-0011 D2 (`app/guardrails.py`).
- **Output-side Guardrails (LLM completion filtering).** Phase 1.5+ per ADR-0011 D2 scope.
- **Per-tenant audit-log query redaction hook.** Phase 1.5 trigger at first real-data tenant onboard per ADR-0011 D8.
- **Redis-backed slowapi for prod rate limit.** Phase 1.5/Phase 2 with prod rollout per ADR-0011 D4.

## Verification

This manifest is complete when:
- Every requirements.txt delta in D1 is in the lockfile.
- Every import path in D2 resolves on a fresh `pip install`.
- Every config knob in D3 has a default in `config.py` and an env-var override path.
- The compose snippet in D4 boots an atlas-local 8.0.8 container.
- The DDL in D5 produces two `status: READY` indexes + two restricted DB roles.
- Each M2-NN ticket in D6 has a PR and a passing test.
