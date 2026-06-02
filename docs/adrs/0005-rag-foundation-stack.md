# ADR 0005 — RAG foundation stack (LangChain v1.0 + Bedrock embeddings + MongoDB Atlas Local + FAR UCF mapping)

Date: 2026-06-01
Status: Proposed (Phase A of retrieval-system planning; B/C/D ADRs follow)
Decision-makers: FDE pair (delivery lead + author)
Phase: 1 — AI Adoption · Milestone M2 (Grounded Retrieval) groundwork
Related: ADR-0003 (pilot endpoint) · ADR-0004 (review remediation) · PRD §6 REQ-RAG-1..4 · PRD §7 principles (grounded-or-withheld, eval-as-the-gate, FedRAMP-safe)

## Context

M2 needs a retrieval substrate that answers FAR/DFARS questions with citations and survives multi-tenant isolation testing (REQ-RAG-3). Phase A locks the foundation stack only — chunking, retrieval pattern selection, re-ranking, index management, security/tenancy, eval, observability are deferred to ADR-0006 through ADR-0009.

Four foundation choices were on the table: (1) LangChain version + retrieval primitives, (2) Bedrock embedding model, (3) MongoDB deployment with vector capability, (4) how FAR's Uniform Contract Format maps onto retrieval boundaries. All four are settled here.

## Decisions

### D1 — LangChain v1.0 as the agent + retrieval framework

Adopt `langchain` v1.0 core. Legacy `LLMChain`, `Retriever` classes, and LCEL/Runnable composition patterns are deprecated in v1.0 core and live in the separate `langchain-classic` package. The v1.0-recommended RAG shape is **retrieval-as-a-tool inside `create_agent`**, not a standalone Retriever wired through a Chain.

Source — LangChain v1.0 migration guide (https://docs.langchain.com/oss/python/migrate/langchain-v1), quoted: *"If you were using any of the following from the `langchain` package, you'll need to install `langchain-classic` and update your imports: Retrievers (e.g. `MultiQueryRetriever` or anything from the previous `langchain.retrievers` module)."*

Source — RAG guide (https://docs.langchain.com/oss/python/langchain/rag), quoted: *"One formulation of a RAG application is as a simple agent with a tool that retrieves information."*

Packages pinned:
- `langchain` (v1.0 core — agents, tools, chat_models, embeddings, messages)
- `langchain-aws` — `ChatBedrockConverse`, `BedrockEmbeddings` (https://docs.langchain.com/oss/python/integrations/providers/aws)
- `langchain-mongodb` — `MongoDBAtlasVectorSearch`, `MongoDBAtlasHybridSearchRetriever` (https://www.mongodb.com/docs/atlas/ai-integrations/langchain/)
- **Not** `langchain-classic` — only install if a future ADR needs a deprecated retriever class.

`services/ai-orchestrator/app/legacy_chain.py` becomes ineligible for any new code path. W2 Mon scheduled modernization stands.

### D2 — `amazon.titan-embed-text-v2:0` at 512 dimensions as the embedding model

Pin model ID `amazon.titan-embed-text-v2:0`. Pin `output_dimensions=512`.

Rationale (all sourced from `docs.aws.amazon.com`):
- **Same auth as chat client.** Bedrock bearer-token (`AWS_BEARER_TOKEN_BEDROCK`) + `boto3.client("bedrock-runtime").invoke_model(modelId=...)` works identically for embeddings — no new auth wiring. (https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html)
- **8K-token context window** lets a FAR section embed as one logical unit. AWS guidance, quoted: *"for retrieval tasks, it is recommended to segment documents into logical segments, such as paragraphs or sections."* Cohere v3's 512-token cap would force splitting mid-section. (https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)
- **GovCloud-eligible** (us-gov-east-1 / us-gov-west-1) — only embedder available there. Keeps Phase-2 FedRAMP-High path open.
- **Configurable dimensions (1024 / 512 / 256).** AWS publishes 1024 as default; 512 is the documented cost lever. Halves Atlas vector index storage + per-query cost vs 1024. Escalate to 1024 only on eval regression.

Re-ranking model — **default `amazon.rerank-v1:0` (Amazon Rerank 1.0), $1.00/1K queries**. Cohere Rerank 3.5 ($2.00/1K) becomes the eval-baseline / escalation option, swapped in only if Phase D RAGAS gate shows Amazon Rerank under-recall.

Rationale: half the per-query cost on the hairpin budget, same `boto3.client("bedrock-agent-runtime").rerank(...)` call shape — only `modelArn` differs. Source: https://docs.aws.amazon.com/bedrock/latest/userguide/rerank-supported.html — both Amazon Rerank 1.0 and Cohere Rerank 3.5 invoke through the Bedrock Rerank API on `bedrock-agent-runtime`. Per-query prices confirmed on https://aws.amazon.com/bedrock/pricing/.

**Regional consequence**: Amazon Rerank 1.0 is NOT available in `us-east-1`. Quote from the rerank-supported docs: *"The Amazon Rerank 1.0 model is not supported in the US East (N. Virginia) AWS Region. You can only use the Cohere Rerank 3.5 model in this Region."* Available regions: `us-west-2`, `ca-central-1`, `eu-central-1`, `ap-northeast-1`. The Phase 1 deployment region for rerank therefore becomes `us-west-2` (matches existing chat-client cross-region inference profile `us.anthropic.claude-sonnet-4-5-...` which already routes through us-west-2 — see ADR-0003 and ADR-0004 M10).

Neither reranker is available in GovCloud. If Phase 2 lands on FedRAMP-High / GovCloud, both reranker options drop and the fallback is LLM-as-judge rerank (likely Nova Micro / `amazon.nova-micro-v1:0` — GovCloud-eligible via `us-gov-west-1` in-region per its model card). Captured here so the Phase-2 ADR knows the constraint exists.

**Not** wrapped by `langchain-aws` — rerank is a direct `boto3.client("bedrock-agent-runtime").rerank(...)` call regardless of which reranker model is picked. Wiring details (when to trigger, top-K to rerank, score threshold for withhold-and-escalate) deferred to ADR-0007.

**Open item:** on-demand $/1K-token for Titan v2 embeddings did not render on the pricing page in two fetches; verify before committing to a per-tenant cost projection. Historically Titan v2 has been the cheapest text-embedder on Bedrock.

### D3 — Replace stock `mongo` container with `mongodb/mongodb-atlas-local:8.0.8`

Replace the `mongo:latest` service in `infra/docker/docker-compose.yml` with `mongodb/mongodb-atlas-local:8.0.8`. Single container serves both transactional collections (current usage) and vector / Atlas Search indexes (new M2 usage) — no second datastore.

MongoDB 8.0 chosen specifically to unlock `$rankFusion` (Reciprocal Rank Fusion hybrid stage) — required by `langchain-mongodb`'s `MongoDBAtlasHybridSearchRetriever`. `$rankFusion` minimum version: MongoDB 8.0. (https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/) 8.2 was the alternative but adds only `$scoreFusion` and increases risk surface for unrelated regressions.

Compose snippet (verbatim shape from MongoDB docs at https://www.mongodb.com/docs/atlas/cli/current/atlas-cli-deploy-docker/):

```yaml
services:
  mongodb:
    hostname: mongodb
    image: mongodb/mongodb-atlas-local:8.0.8
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

Connection string requires `?directConnection=true` (single-node replica set).

**Migration plan (no data loss):**
1. `mongodump` from current stock `mongo` container into a host-mounted dump dir.
2. Swap image to `mongodb/mongodb-atlas-local:8.0.8` with **empty** named volumes (do NOT reuse `/data/db` bytes — on-disk format compatibility is undocumented).
3. `mongorestore` into the new container.
4. Run seed scripts to call `db.<collection>.createSearchIndex(...)` for both vector and BM25 indexes (DDL deferred to ADR-0006).
5. Smoke test: existing app traffic still reads/writes; new vector queries succeed.

This satisfies guideline-4 ("rollover plan, no information loss"). Item 5 (no postgres volume mount — a deliberate brownfield-debt reinforcement gap) is unrelated and stays.

**Production rollover:** Atlas Local is dev-only. MongoDB docs, quoted: *"Local Atlas deployments reside on your computer and provide a non-production environment for development."* (https://www.mongodb.com/docs/atlas/cli/current/atlas-cli-local-cloud/) Prod = cloud Atlas; the index definitions are portable JSON, so the Phase-1.5 / Phase-2 promotion path is dump/restore + re-create indexes — no schema rewrite.

### D4 — FAR UCF maps onto retrieval boundaries as drafting-target vs source-corpus

Per FAR 15.204-1 (https://www.acquisition.gov/far/15.204-1), the Uniform Contract Format has four Parts spanning Sections A–M:

| Part | Sections | Role in our RAG |
|---|---|---|
| I — The Schedule | A, B, C, D, E, F, G, H | C / H are **drafting targets** (LLM-generated); A, B, D, E, F, G are typically operator-entered. |
| II — Contract Clauses | I | **Source corpus** — FAR Part 52 clauses retrieved into Section I. |
| III — Attachments | J | List of attachments. Light retrieval target. |
| IV — Reps/Instructions | K, L, M | **K**: reps/certs templates (source). **L, M**: drafting targets. |

**Drafting targets** (LLM writes, must be grounded + cited): Sections C, H, L, M.
**Source corpus** (we retrieve over): FAR Part 52 clauses, historical Section C SOWs, Section M evaluation factor templates, Section K reps/certs templates.

**Cross-section invariant to enforce post-draft:** Section L instructions MUST align with Section M evaluation factors (FAR 15.204-5). This is a retrieval-AND-validation rule, not pure retrieval — implementation deferred to ADR-0008 (HITL + audit gates).

**Boundary fact:** Part IV (K–M) is in the solicitation but NOT in the awarded contract document. FAR 15.204-1, quoted: *"Upon contract award, Part IV remains in the contract file but is not physically include[d] in the resulting contract document."* Retention/audit metadata must distinguish "in solicitation" from "in contract" — relevant for ADR-0008 OIG-replay design.

### D5 — FAR corpus seeded from a one-time download, checked into `docs/reference/far/`

Download FAR XML/HTML from acquisition.gov once and check the snapshot into `docs/reference/far/`. The seed script reads the local snapshot to build the RAG corpus. No live HTTP fetch in seed or test paths.

Why: reproducibility (CI doesn't break on acquisition.gov URL changes), offline-friendly (cohort doesn't need network for first-day work), and the corpus becomes a versioned artifact (snapshot date is part of the audit trail per PRD "auditable by default").

The PRD constraint "synthetic data only" applies to **vendor / proposal / award data**, not to public regulatory text. FAR/DFARS are public-domain US-government regulations — embedding them is not a synthetic-data violation.

## Consequences

**Positive:**
- One framework (LangChain v1.0) for both M1 drafting and M2/M3 retrieval+agent flows — no per-milestone framework switch.
- One datastore (atlas-local) serves OLTP + BM25 + vector — cuts infra surface vs running e.g. Postgres + pgvector + a separate search service.
- Hybrid retrieval (BM25 + vector + RRF) is available out-of-box via `langchain-mongodb` — satisfies guideline-6 (no homegrown fusion code).
- GovCloud-eligible embedder + cloud-Atlas migration path keeps Phase-2 FedRAMP-High feasible.

**Negative / known tradeoffs:**
- Atlas Local is dev-only — there is no prod story until cloud Atlas spins up (Phase 1.5 or Phase 2 decision).
- `cohere.rerank-v3-5:0` is not wrapped by `langchain-aws`; if ADR-0007 picks it, we call `bedrock-agent-runtime.rerank()` directly. Small custom adapter; not a deal-breaker.
- Titan v2 @ 512 dims is a quality-vs-cost bet. If M2 eval baseline shows weak recall, the lever is "bump to 1024 dims" before the lever is "change embedding family."
- `langchain-classic` install is reserved as an escape hatch for any pre-v1 retriever class we discover we still need — currently we don't expect to.

**Untouched brownfield-debt items** (intentional — none of D1–D5 modernize the SB 2.7.18 / Java 11 baseline, none touch the deliberate compose drift documented in CLAUDE.md):
- Item 11 (`:latest` on the other 4 Dockerfiles) stays.
- `BEDROCK_MODEL_ID` three-source drift stays (W2 Mon cohort work).
- Postgres volume mount gap stays.

## Open Questions (deferred to later ADRs)

| Q | Owner ADR |
|---|---|
| Chunk size, chunk overlap, chunk schema (text + metadata fields) | ADR-0006 |
| Per-FAR-section retrieval pattern (when dense, when sparse-only, when hybrid) | ADR-0006 |
| Re-ranking trigger threshold + model choice (Cohere Rerank 3.5 vs cross-encoder vs LLM-as-judge rerank) | ADR-0007 |
| Index lifecycle (create / rebuild / hot-swap / startup cache) | ADR-0007 |
| Multi-tenant isolation primitive (`$vectorSearch` filter on `tenant_id` + test proof for REQ-RAG-3) | ADR-0008 |
| Citation grounding format + OIG-replayable audit log shape | ADR-0008 |
| HITL gates inside retrieval flow | ADR-0008 |
| RAGAS metrics + LLM-as-judge eval wiring | ADR-0009 |
| Observability (OTel spans through agent + retriever + Bedrock calls) | ADR-0009 |
| Failure modes + withhold-and-escalate logic (REQ-RAG-2) | ADR-0009 |
| Bedrock embedding $/1K-token verification (pricing page would not render) | This ADR — confirm before per-tenant cost projection |

## Verification

- D1: `pip show langchain langchain-aws langchain-mongodb` shows v1.x.x.
- D2: `services/ai-orchestrator/app/bedrock_client.py` adds an `EmbedClient` that targets `amazon.titan-embed-text-v2:0` with `dimensions=512` and reuses the existing bearer-token auth path.
- D3: `docker compose up` brings up the atlas-local container; `mongosh "$URI?directConnection=true"` returns OK; `db.runCommand({buildInfo:1}).version` returns `8.0.8`.
- D4: `docs/reference/far/MANIFEST.md` lists the Part → Section mapping above and the snapshot date.
- D5: `docs/reference/far/` exists with FAR Part 15.2 + Part 52 content; seed script ingests from there only.
