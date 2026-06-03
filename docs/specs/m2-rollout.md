# M2 Grounded Retrieval — Implementation Rollout Spec

**Phase 1 · Milestone M2** · Implementer entry point: [`docs/adrs/0010-rag-implementation-manifest.md`](../adrs/0010-rag-implementation-manifest.md)

This spec decomposes the M2 (Grounded Retrieval) ADR catalog (ADR-0005..0011) into a PR-ordered execution plan with blockers, branching strategy, commit conventions, label gates, and CI gates. It is the bridge from planning (ADRs) to delivery (PRs).

## Dependency graph

Three slices. Slice A and Slice B run in parallel; Slice C is fully serial after both land.

```
Slice A — LangChain v1 cutover            Slice B — Atlas migration
   (Item 5 flip blocks A2)                    (no debt blocker)

   A1: modernize legacy_chain.py             B1: atlas-local container swap
        + flip Item 5 lockfile                    + dump/restore migration
              │                                          │
              ↓                                          ↓
   A2: bump LangChain v1 + langchain-aws        B2: empty createSearchIndex
        + langchain-mongodb                          + DB roles for audit_log
        + langchain-text-splitters                   (audit_log empty, roles ready)

              │                                          │
              └────────────────────┬─────────────────────┘
                                   ↓
                          Slice C — initial retrieval (11 PRs, serial)
```

## Critical blockers

1. **Item 5 brownfield-debt blocks A2 package bump.** `legacy_chain.py` uses pre-v1 `LLMChain.run()`. Bumping `langchain` to ≥1.0 breaks it because `LLMChain` moved to `langchain-classic` (which ADR-0005 D1 explicitly refuses to install). A1 must flip Item 5 in `docs/debt-lockfile.yml` AND modernize `legacy_chain.py` to v1 patterns before A2 can ship.
2. **Atlas container swap blocks all data ops.** `mongo:latest` has no `$vectorSearch` / `$rankFusion`. B1 must complete before any corpus ingest (C-tickets).
3. **A2 + B2 both block C1.** No C-ticket starts until both A and B slices are merged to `main`.

## PR-ordered execution plan

### Slice A — LangChain v1 cutover (2 PRs)

| # | Branch | Title | Type | Labels | Notes |
|---|---|---|---|---|---|
| **A1** | `cj/m2-a1-modernize-legacy-chain` | Modernize `legacy_chain.py` to v1 patterns + flip Item 5 lockfile | `debt(item-5):` | `debt-touch-approved` | Per CLAUDE.md legitimate-modernization flow: flip `locked: true → false` in `docs/debt-lockfile.yml`, fill PR template YES branch. Item 5 locked-failing test must transition to passing. |
| **A2** | `cj/m2-a2-bump-langchain-v1` | Bump LangChain to v1 + add aws/mongodb/text-splitters deps | `feat(deps):` | — | `requirements.txt` deltas per ADR-0010 D1. Drop `pinecone-client` (Item 7 also flips here per CLAUDE.md note — separate Item 7 PR may be needed depending on schedule). |

### Slice B — Atlas migration (2 PRs)

| # | Branch | Title | Type | Labels | Notes |
|---|---|---|---|---|---|
| **B1** | `cj/m2-b1-atlas-local-cutover` | Replace `mongo:latest` with `mongodb/mongodb-atlas-local:8.0.8` + dump/restore | `feat(infra):` | — | `docker-compose.yml` swap per ADR-0010 D4. Spec step for dump → restore → smoke. Connection string adds `?directConnection=true`. |
| **B2** | `cj/m2-b2-create-search-indexes` | Seed-time `createSearchIndex` script + `audit_log` DB roles | `feat(infra):` | — | DDL per ADR-0010 D5. Indexes empty until C3 ingest. Roles (`auditLogWriter`, `auditLogReader`) per ADR-0008 D3. |

### Slice C — Initial retrieval (11 PRs, serial)

| # | Branch | Title | Type | Labels | Notes |
|---|---|---|---|---|---|
| **C1** | `cj/m2-c1-far-snapshot-ingest` | FAR Part 15.2 + Part 52 snapshot + signed `MANIFEST.sha256` + `synthetic-data-check.yml` | `feat(corpus):` | `far-snapshot-update-approved` | Combines M2-02 + M2-19. Initial corpus + tamper-detection in same PR. |
| **C2** | `cj/m2-c2-chunking-ingest-scan` | Two-stage splitter + ingest-time `chunk_quality_flag` content scan | `feat(ingest):` | — | M2-03 + M2-13. Splitter + indirect prompt-injection defense ship together because the scan runs DURING ingest. |
| **C3** | `cj/m2-c3-bedrock-embeddings` | `BedrockEmbeddings` (Titan v2 @ 512) seed pipeline | `feat(embed):` | — | M2-04. Reuses `AWS_BEARER_TOKEN_BEDROCK`. Indexes auto-fill from B2's empty state. |
| **C4** | `cj/m2-c4-retriever-factory` | Hybrid retriever factory + tenant pre-filter + `req_rag_3` locked-passing test | `feat(retrieve):` | — | M2-06. `build_far_retriever(tenant_id=..., ...)` with kw-only required tenant_id. Test for same-content cross-tenant impossibility. |
| **C5** | `cj/m2-c5-query-classifier` | Regex/keyword query classifier + per-query RRF weights | `feat(retrieve):` | — | M2-07. Sets `vector_weight` / `fulltext_weight` per ADR-0006 D3 table. |
| **C6** | `cj/m2-c6-rerank-gate` | Amazon Rerank 1.0 wiring + threshold gate + audit-log skeleton | `feat(rerank):` | — | M2-08 + part of M2-09. Rerank client in us-west-2. Gate logic for withhold/HITL/pass. Audit-log schema/insert path stubbed. |
| **C7** | `cj/m2-c7-audit-citation-verify` | Append-only `audit_log` finalized + citation hard-fail + `verify-bedrock-logging-disabled.sh` CI | `feat(audit):` | — | Rest of M2-09 + M2-15. DB role privileges actually applied. Citation verifier checks chunk_ids against retrieved set. CI guard asserts Bedrock invocation logging stays OFF. |
| **C8** | `cj/m2-c8-query-guardrails` | Hand-built query-side `QueryGuardrails` (regex layer + Nova Micro judge for borderline) | `feat(guardrails):` | — | M2-14. Per ADR-0011 D2. `JAILBREAK_PATTERNS` + length cap + LLM-as-judge layer. |
| **C9** | `cj/m2-c9-retrieve-endpoint` | `/retrieve` FastAPI endpoint + `slowapi` rate-limit + retrieval caps | `feat(api):` | — | M2-12 + M2-16. First end-to-end HTTP path. Pass / HITL / withhold branches return distinct shapes. |
| **C10** | `cj/m2-c10-adversarial-tenant-tests` | Adversarial cross-tenant query cases extending `req_rag_3` marker | `test(req_rag_3):` | — | M2-18. Three crafted-query cases per ADR-0011 D6. CI-blocking. |
| **C11** | `cj/m2-c11-docs-spec` | README prereqs + `.env.example` + cohort spec | `docs:` | — | M2-20. Notes synthetic-data CI guard + FAR manifest workflow. NO host-disk-encryption mandate (ADR-0008 D1 fix). |

After C11 merges, **initial retrieval operation is end-to-end functional**: a query against a tenant's FAR corpus returns top-5 cited chunks, withholds on low confidence, audits to `audit_log`, and rejects jailbreak/oversize/over-rate-limit input.

### Deferred from "initial retrieval" minimum

These are M2 work but NOT blockers for the first end-to-end retrieval path:

| Ticket | When | Why deferred |
|---|---|---|
| **M2-10 HITL middleware** | After C9 once `issue_solicitation` tool exists | `/retrieve` endpoint is direct retriever-invoke; no `create_agent` path yet |
| **M2-11 MongoDBSaver checkpointer** | With M2-10 | Same — only needed when agent + HITL pause is wired |
| **M2-17 Pydantic strict tool-arg** | With M2-10 | Only needed if `@tool`-decorated functions are exposed via agent |
| **RAGAS eval gate (ADR-0009 D1)** | After C11 once retrieval ships | Eval set generated from FAR snapshot; threshold ratchet vs main |
| **M2-21 cloud-Atlas migration** | Phase 1.5 trigger | Only when real-data ingest is approved |

## Branching strategy (durable rule)

**Pattern:** `cj/m2-<slice>-<ticket>-<short-description>` — e.g., `cj/m2-c4-retriever-factory`.

Extends the general CLAUDE.md convention (`<initials>/<short-description>`) by encoding slice + ticket position for M2's multi-PR rollout. Once M2 is done, future phases re-instantiate the pattern (`cj/m3-...` etc.) or fall back to the general form for one-offs.

**One PR per ticket.** No long-lived feature branches, no integration branches. Each PR targets `main` directly. Sequential merge for Slice C; Slice A and Slice B can land in parallel (different files, no review conflict).

**Each PR cites the ADR section it implements** in the PR description (e.g., "Implements ADR-0006 D1 + D2 + ADR-0011 D1.1"). Reviewers can verify the implementation matches the locked decision.

## Commit type / scope conventions

| Pattern | When |
|---|---|
| `debt(item-N): ...` | Modernization commits that flip a brownfield-debt lockfile entry. CLAUDE.md mandate. A1 is the only known one in this rollout. |
| `feat(deps): ...` | Package version bumps that enable new capability (A2). |
| `feat(infra): ...` | Container / index / role infrastructure (B1, B2). |
| `feat(corpus|ingest|embed|retrieve|rerank|audit|guardrails|api): ...` | New capabilities in slice C — scope per ticket table. |
| `test(<marker>): ...` | Test-only additions (C10). |
| `docs: ...` | Doc / spec updates (C11). |
| `fix(<scope>): ...` | Bug fixes encountered mid-rollout. NOT for scope-creep work. |
| `chore: ...` | Sweeping maintenance. Reserved — not used in this rollout. |

## Label gates

| Label | Required on | Source |
|---|---|---|
| `debt-touch-approved` | A1 only | CLAUDE.md legitimate-modernization flow |
| `far-snapshot-update-approved` | C1 + any future FAR-corpus update | ADR-0011 D7 |
| (standard review approval) | all other PRs | repo default |

## CI gates that must stay green on every PR

| Gate | Lands in | Behavior |
|---|---|---|
| Existing `debt-enforcement.yml` (locked-failing tests) | already present | Tests for Items 1-12 must keep failing **except Item 5 after A1** (which transitions to passing per the lockfile flip) |
| `synthetic-data-check.yml` | C1 | Rejects PRs that import non-allowlisted corpus prefixes |
| `verify-far-snapshot-manifest.sh` | C1 | SHA-256 manifest check on `docs/reference/far/` |
| `req_rag_3` marker — cross-tenant impossibility | C4 (locked-passing); C10 adds adversarial cases | MUST stay green. Equivalent to a debt-style lock in the opposite direction. |
| `verify-bedrock-logging-disabled.sh` | C7 | Asserts Bedrock model invocation logging configuration is disabled |
| `rag-eval-gate.yml` (RAGAS one-way threshold ratchet) | After C11 (out of initial-retrieval scope) | Faithfulness / Answer Relevancy / Context Precision / Context Recall ratchet vs main |

## Estimated rollout shape

15 PRs total to reach end-to-end initial retrieval:
- 4 pre-tickets (A1, A2, B1, B2) — Slice A + B
- 11 C-tickets (C1..C11) — Slice C

Slices A and B run in parallel → 2 PRs to first merge each. Slice C is serial → 11 PRs to first merge each. Critical-path PR count = 2 (whichever of A/B is slower) + 11 = ~13 sequential merges.

Per-PR work is small enough that each lands in a single working session under normal review SLA. Stack of PRs against `main` keeps everyone unblocked except the literal next-up reviewer.

## What this spec does NOT cover

- M3 (Agentic source-selection workflow) — separate PRD milestone.
- Phase 2 modernization items (SB→4.0.x, Java 21, circuit breaker, OTel rollout). PRD §4 OOS.
- Other brownfield-debt item flips beyond Item 5 — those have their own scheduled weeks per `docs/brownfield-debt.md`.
- Cloud-Atlas migration (M2-21 / Phase 1.5 trigger).

## When to update this spec

- **Before opening A1**: confirm the Item 5 lockfile diff shape against the actual `docs/debt-lockfile.yml` (this spec assumes the flow described in CLAUDE.md; verify the lockfile field names match).
- **After each PR merges**: tick the ticket off; note any deviation from the planned shape so the next planning session can learn.
- **If a C-ticket discovers a missing dependency**: re-thread the order here, not in scattered comments.
