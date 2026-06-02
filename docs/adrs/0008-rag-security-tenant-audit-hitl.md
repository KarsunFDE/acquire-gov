# ADR 0008 — RAG security, multi-tenant isolation, OIG audit, HITL gates

Date: 2026-06-01
Status: Proposed (Phase C of retrieval-system planning)
Decision-makers: FDE pair (delivery lead + author)
Phase: 1 — AI Adoption · Milestone M2 (Grounded Retrieval) + foreshadows M3 (Agentic)
Related: ADR-0005..0007 · PRD §6 REQ-RAG-3 (no cross-tenant retrieval) · PRD §7 (auditable by default, authority over accuracy) · FAR 4.805 · FAR 15.206 · FAR 15.308 · FAR 5.705

## Context

Phase A/B locked the retrieval stack. Phase C settles the four cross-cutting concerns that turn a retrieval system into one that can defend itself in front of an OIG auditor: encryption posture, tenant isolation proof, immutable audit log shape, and HITL gates wired to statutorily-reserved decisions. This ADR captures all four because they are deeply entangled — the audit-log schema depends on the tenant filter, which depends on the encryption boundary, which depends on the HITL state's persistence target.

## Decisions

### D1 — Atlas Local has no encryption-at-rest; Phase 1 absorbs the gap with three controls

**Finding.** MongoDB Community Edition has **no native WiredTiger encryption-at-rest**. Source: https://www.mongodb.com/docs/manual/core/security-encryption-at-rest/, quoted: *"Available in MongoDB Enterprise only."* The `mongodb/mongodb-atlas-local` Docker image is built on Community Edition, so the atlas-local container chosen in ADR-0005 has **no application-layer encryption-at-rest**.

**Bedrock side is clean** (no compensating-control work needed there). Source: https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html, quoted: *"Because the model providers don't have access to those accounts, they don't have access to Amazon Bedrock logs or to customer prompts and completions."* TLS 1.2+ in transit (Bedrock docs: *"all inter-network data in transit supports TLS 1.2 encryption"*), KMS encryption for stored Bedrock artifacts, FIPS endpoints available for federal use.

**Two Phase-1 controls absorb the gap:**

1. **Data-class constraint (already in PRD §7).** Phase 1 ingests **synthetic data only**, plus the **public-domain FAR/DFARS snapshot** from `docs/reference/far/`. No real vendor PII, no real proposal content, no real CO identities. Encryption-at-rest is therefore a defense-in-depth gap, not a confidentiality breach.
2. **Hard block on real-data ingest.** Add a CI check that scans `docs/reference/` and seed data for anything not matching `synthetic_*` / `FAR-*-snapshot` / `dfars-*` prefixes — reject PRs that import real corpora. This makes "we accidentally ingested real data into atlas-local" a CI-caught mistake, not a runtime discovery.

**Host-disk encryption (BitLocker / FileVault / LUKS) NOT added as a cohort prereq.** Pushing security requirements onto cohort dev hosts is AI-security hardening of legacy debt — PRD §4 + CLAUDE.md explicitly carve that out as Phase 2 work. The synthetic-data constraint (#1) is the PRD-mandated Phase-1 mitigation; doubling up with a host-encryption mandate is goldplating the legacy gap. If real data ever enters, the answer is cloud Atlas, not BitLocker.

**Migration to cloud Atlas** (Phase 1.5 / Phase 2) gives us encryption-at-rest by default (cloud Atlas managed keys) with BYO-KMS as an upgrade option. The promotion path is dump/restore + re-create indexes (ADR-0005 D3).

**Queryable Encryption** (https://www.mongodb.com/docs/manual/core/queryable-encryption/, quoted: *"Queryable Encryption equality and range queries are fully supported in production."*) is GA in MongoDB 8.0+ and works in Community Edition — reserved as the Phase-1.5+ lever **only** if real PII enters the system before cloud-Atlas migration. Not Phase 1.

### D2 — Single DB + `tenant_id` filter + factory-enforced isolation; locked-passing pytest gate

**Pattern.** One MongoDB database. One `chunks` collection. Every chunk has a required `tenant_id` field. The vectorSearch index declares `tenant_id` as a `filter` field (ADR-0006 D2 schema already does this). Every retrieval call passes `tenant_id` to `$vectorSearch.filter` → pre-filter executes **before** the ANN scan.

Source: https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-stage/. The `filter` field accepts MQL operators (`$and`, `$eq`, `$in`). MongoDB docs note: *"Filtered queries are typically slower than an otherwise equivalent unfiltered query"* — accepted; isolation is structural, not advisory.

**Factory enforcement.** `services/ai-orchestrator/app/retrieval.py` exposes one factory:

```python
def build_far_retriever(*, tenant_id: str, vector_weight: float = 1.0, fulltext_weight: float = 1.0):
    if not tenant_id:
        raise ValueError("tenant_id is required — REQ-RAG-3 isolation cannot be bypassed")
    return MongoDBAtlasHybridSearchRetriever(
        vectorstore=vector_store,
        search_index_name="far_search_idx",
        k=20,
        vector_weight=vector_weight,
        fulltext_weight=fulltext_weight,
        pre_filter={"tenant_id": tenant_id},
    )
```

`tenant_id` is **keyword-only required** (no positional fallback, no default). Constructing a retriever without it is a literal `TypeError` at call time. Code review pattern: any direct `MongoDBAtlasHybridSearchRetriever(...)` constructor outside this factory is a review-blocking pattern.

**Locked-passing pytest gate (CI-blocking, REQ-RAG-3 proof):**

```python
@pytest.mark.req_rag_3
def test_cross_tenant_retrieval_impossible():
    seed_chunk(tenant_id="tenant_A", text="FAR L.5 says X — proprietary to A")
    seed_chunk(tenant_id="tenant_B", text="FAR L.5 says X — proprietary to B")
    retriever = build_far_retriever(tenant_id="tenant_A")
    results = retriever.invoke("what does L.5 say")
    assert results, "tenant_A should retrieve its own chunks"
    assert all(d.metadata["tenant_id"] == "tenant_A" for d in results), \
        f"REQ-RAG-3 violated — cross-tenant chunk leaked: {[d.metadata['tenant_id'] for d in results]}"
```

This is the **inverse** of the brownfield-debt locked-failing tests: it must stay **green** on every PR. A `req_rag_3` pytest marker + a CI step that runs `pytest -m req_rag_3` makes the gate explicit. If this test goes red, no PR merges.

**Why not "separate DB per tenant" or "separate collection per tenant":**
- Separate DB multiplies index storage (~2x per tenant, each with its own vectorSearch index — expensive and slow to seed on every tenant onboard).
- Separate collection avoids the shared-collection-accident class of bug but still needs every tool to pick the right collection — same logical surface area as `tenant_id` filter, more infra to manage.
- Phase 1 has a low tenant count; single-DB + filter is the right complexity-cost tradeoff. Phase-2 escalation lever exists if Atlas $vectorSearch starts struggling at scale.

### D3 — Append-only `audit_log` with hashed prompts + raw citations

**Retention floor.** FAR 4.805 (https://www.acquisition.gov/far/subpart-4.8, Table 4-1): contracts and related records (including successful and unsuccessful proposals, evaluation documents, source selection materials) — **6 years after final payment**. Canceled solicitations — **6 years after cancellation**. Audit-log retention target: 6 years post-event minimum.

**Append-only enforcement** via MongoDB role privileges, not application code:

```javascript
db.createRole({
  role: "auditLogWriter",
  privileges: [{
    resource: { db: "acquire_gov", collection: "audit_log" },
    actions: [ "insert", "find" ]      // explicitly NO update, NO remove
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
```

The orchestrator's service user binds to `auditLogWriter`. OIG / CO replay users bind to `auditLogReader`. **No role grants update or remove** — append-only enforced at the database level. App code cannot bypass it.

**Schema (v1):**

```python
{
    "_id":           ObjectId(),
    "ts":            ISODate("..."),
    "tenant_id":     "agency-xyz",                     # REQ-RAG-3 required
    "request_id":    "<correlation id>",                # trace across services
    "actor":         {"user_id": "...", "role": "CO|specialist|reviewer", "session_id": "..."},
    "action":        "retrieval_and_generate",          # | retrieval_only | issue_solicitation | amend_solicitation | hitl_decision
    "request":       {"query": "...", "query_hash": "<sha256>"},
    "retrieval":     {
        "retriever_class":  "MongoDBAtlasHybridSearchRetriever",
        "vector_weight":    1.0,
        "fulltext_weight":  1.0,
        "candidates":       [{"chunk_id": ObjectId, "vector_score": 0.82, "fulltext_score": 0.71}, ...],
        "rerank_model":     "amazon.rerank-v1:0",
        "rerank_top":       [{"chunk_id": ObjectId, "relevance_score": 0.74}, ...],
        "gate_decision":    "pass|hitl|withhold",
    },
    "generation":    {
        "model":            "anthropic.claude-sonnet-4-5",   # ADR-0003 pilot
        "prompt_hash":      "<sha256>",                       # NOT raw prompt — see rationale
        "completion_hash":  "<sha256>",                       # NOT raw completion
        "input_tokens":     1234,
        "output_tokens":    567,
        "citations":        [                                  # RAW, not hashed — replay needs these
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
    "outcome":       "draft_returned|withheld|hitl_pending|hitl_approved|hitl_rejected",
    "schema_version": 1,
}
```

**Why hash prompt + completion, keep citations raw:**
- Hashes: 6-year × ~10K queries/day rough envelope = ~22M records. Raw prompts (1-4 KB each) blow storage. SHA-256 is 32 bytes. Non-repudiation preserved — replay engine recomputes hash from `(query, citations, model, prompt_template_version)` and verifies match.
- Citations: raw chunk_id + FAR section/clause/snapshot_date are **the grounding proof**. Hashing them defeats the purpose — OIG needs to see *which FAR section grounded which sentence*. Storage cost is bounded (small structured object per citation).

**Schema versioning.** `schema_version: 1` field locked from day one. Future schema evolution is additive (new fields → bump version, old records still readable); destructive evolution (rename / remove field) is blocked by the append-only role privileges and the retention period.

### D4 — HITL middleware: hard-gate statutorily-reserved tools; soft-gate confidence-band

**Hard gates** (always interrupt regardless of model confidence — PRD "authority over accuracy"):

| Tool | Statutory authority | Interrupt? |
|---|---|---|
| `issue_solicitation` | FAR 5.705 (publicizing) | **Always** |
| `amend_solicitation` | FAR 15.206 (amending solicitations) | **Always** |
| `award_contract` (M3 territory) | FAR 15.308 (Source Selection Decision) | **Always** |
| `sign_ssa_document` (M3) | FAR 15.308 | **Always** |
| `retrieve_far_context` | none | Never (read-only) |
| `draft_section` | none — output is a draft, not a commitment | Never (soft-gate via response flag) |

**Soft gate** (no interrupt; response carries flag): rerank-gate `hitl` band (ADR-0007 D2 — top relevance score 0.3 ≤ score < 0.5) sets `requires_human_review: true` in the API response. Agent generation proceeds; CO sees the flag on the draft. Soft-gate decisions still write to `audit_log` with `action: "retrieval_and_generate"` and `retrieval.gate_decision: "hitl"`.

**Implementation** per https://docs.langchain.com/oss/python/langchain/human-in-the-loop, quoted: *"The middleware will interrupt execution when a tool call matches an action in the mapping"* and *"requires a checkpointer to persist the graph state across interrupts."*

```python
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

checkpointer = MongoDBSaver(MongoClient(MONGO_URI))

agent = create_agent(
    model=chat_model,
    tools=[retrieve_far_context, draft_section, issue_solicitation, amend_solicitation],
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "issue_solicitation":  {"allowed_decisions": ["approve", "reject"]},
                "amend_solicitation":  {"allowed_decisions": ["approve", "reject"]},
                # retrieve_far_context, draft_section NOT interrupted
            },
        ),
    ],
    checkpointer=checkpointer,
)
```

**Multi-day pause survival.** Source: https://docs.langchain.com/oss/python/langgraph/persistence, quoted: *"A thread is a unique ID or thread identifier assigned to each checkpoint saved by a checkpointer. It contains the accumulated state of a sequence of runs."* Same `thread_id` resumes the run after arbitrary delay — satisfies PRD M3 requirement *"paused runs survive multi-day human delays."*

### D5 — `MongoDBSaver` checkpointer in the same atlas-local container

**Checkpointer pick: `MongoDBSaver` from `langgraph-checkpoint-mongodb`.** Package source: https://www.mongodb.com/docs/atlas/ai-integrations/langgraph/ — official MongoDB-maintained checkpointer.

```bash
pip install "langgraph-checkpoint-mongodb>=0.4.0"
```

**Why MongoDBSaver, not SqliteSaver / InMemorySaver / PostgresSaver:**
- **Same container as the corpus + audit log.** Zero new infra (no Redis, no Postgres, no SQLite volume to lose). Backup story = MongoDB backup story.
- **Encryption-at-rest gap (D1) applies identically.** Already absorbed. No new variance.
- **Multi-day survival.** Container restart doesn't lose state — atlas-local volume persists. SqliteSaver on a container volume risks loss if volume is wiped during a `docker compose down -v`; Mongo data is the same volume but already in our backup/restore plan.
- **No homegrown code.** MongoDB officially supports it; LangGraph officially documents it. Guideline-6 honored.

**Collections in atlas-local after this ADR lands:**

| Collection | Purpose | Indexes | Notes |
|---|---|---|---|
| `chunks` | RAG corpus (ADR-0006 D2 schema) | `far_vector_idx`, `far_search_idx` | tenant_id filter mandatory |
| `audit_log` | Append-only OIG record (D3) | `{ts:1}`, `{tenant_id:1, ts:-1}`, `{request_id:1}` | role-restricted insert/find only |
| `checkpoints` | LangGraph state (D5) | MongoDBSaver default | one doc per checkpoint |
| `checkpoint_writes` | LangGraph staged writes (D5) | MongoDBSaver default | working state |

**No `tenants` registry collection** — `tenant_id` is caller-asserted per existing pilot pattern (ADR-0004 M9). The retrieval factory (D2) enforces *presence*, not provenance. A tenant-registry collection would cross PRD §4's "Full multi-tenant isolation across all services (Phase 1 covers the retrieval boundary only)" boundary; deferred to a Phase-2 tenant-management ADR if/when needed.

## Consequences

**Positive:**
- REQ-RAG-3 (no cross-tenant retrieval) is **structurally** enforced (index pre-filter), **factory-enforced** (retriever can't be constructed without tenant_id), and **CI-gated** (pytest req_rag_3 marker). Three layers; any single failure mode gets caught.
- Audit log is append-only at the **database role** level — application bugs cannot mutate it.
- Hash-based prompt/completion storage gives 6-year retention math that fits a reasonable storage envelope without losing OIG-replayability.
- HITL state lives in the same MongoDB as the corpus + audit log — single backup target, single recovery procedure.
- Bedrock data-protection posture (TLS 1.2+, KMS, no-training, FIPS endpoints) is documented as the upstream story so a Phase-2 security review can resume from a known baseline.

**Negative / tradeoffs:**
- **Atlas Local has no encryption-at-rest.** Real. Documented. Mitigated by data-class constraint (synthetic + public-domain only) + host-disk encryption prereq + CI ingest-block. NOT solved; the resolution path is the cloud-Atlas migration (Phase 1.5+).
- **Pre-filter slows queries.** MongoDB explicitly notes filtered queries are slower than unfiltered. Phase 1 corpus size is small (~50 MB after FAR Part 15.2 + Part 52 + a synthetic-vendor seed) — query latency is well within the budget. Phase 2 escalation lever: hierarchical indexes per tenant if filter overhead becomes a p95 problem.
- **Hash-based audit storage means full prompt/completion text is NOT recoverable unless the replay engine has the prompt template version + same model version.** If a prompt template is silently changed without bumping `prompt_template_version`, old audit records become unreplayable. Mitigation: template-version field is mandatory in the audit record; ADR-0009 wires a CI check that prompts are version-pinned.
- **CO toil.** Hard-gating every issue/amend/award tool call means the CO is in the loop for every solicitation publication. That's the **intended** behavior — these are statutorily reserved decisions, not workflow friction to optimize away. If CO toil becomes the cohort-feedback signal, the answer is better drafts that get rejected less often, not bypassing the gate.
- **NIST 800-53 AU-3 alignment is asserted, not proven.** NIST control text could not be fetched in this session; the audit schema covers the canonical fields (type/timestamp/identity/success-failure/source/outcome) but a formal control-by-control mapping is deferred to a Phase 1.5 security review.

## Verification

- D1: `.github/workflows/` has a `synthetic-data-check.yml` job that scans for non-allowlisted corpus prefixes and rejects PRs that import real corpora.
- D2: `pytest -m req_rag_3` passes in CI on every PR. Removing it (or changing the test) requires a debt-touch-approved label (same flow as brownfield-debt items).
- D3: `db.createRole` commands captured in `infra/mongo/seed/02-roles.js`. Integration test asserts `update` and `remove` raise `not authorized` for the service user.
- D4: `pytest tests/test_hitl_middleware.py` verifies `issue_solicitation` triggers interrupt + waits for `Command(resume=...)`; `retrieve_far_context` does NOT trigger interrupt.
- D5: `pip show langgraph-checkpoint-mongodb` shows ≥ 0.4.0. After a paused HITL run, restarting the orchestrator container and resuming with the same `thread_id` recovers the agent's pre-interrupt state.
