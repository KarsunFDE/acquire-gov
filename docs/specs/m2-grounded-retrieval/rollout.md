# M2 Grounded Retrieval — Implementation Rollout Spec

**Phase 1 · Milestone M2** · Implementer entry point: [`docs/adrs/0010-rag-implementation-manifest.md`](../../adrs/0010-rag-implementation-manifest.md)

This spec decomposes the M2 (Grounded Retrieval) ADR catalog (ADR-0005..0011) into a PR-ordered execution plan with blockers, branching strategy, commit conventions, label gates, and CI gates. It is the bridge from planning (ADRs) to delivery (PRs).

Companion specs (consume the endpoint + module shapes locked in `m2-grounded-retrieval/rollout.md`'s execution path):

- [`m2-grounded-retrieval/retrieval-pipeline.md`](m2-grounded-retrieval/retrieval-pipeline.md) — implementer-grade pipeline spec consolidating ADR-0005..0011 (endpoint contracts, module layout, failure modes).
- [`m2-grounded-retrieval/eval-harness.md`](m2-grounded-retrieval/eval-harness.md) — RAGAS + Nova-Micro judge + programmatic checks (citation validity, cross-tenant fuzz, latency/token regression). Owns Slice D.
- [`m2-grounded-retrieval/synthetic-corpus.md`](m2-grounded-retrieval/synthetic-corpus.md) — lean synthetic-solicitation corpus + admin ingest pipeline internals.
- [`m2-grounded-retrieval/ui-far-sections.md`](m2-grounded-retrieval/ui-far-sections.md) — Angular FAR UCF wizard expansion + per-section provenance + HITL surfaces + admin ingest UI.

## Dependency graph

Four slices. Slice A and Slice B run in parallel pre-tickets; Slice C is the serial retrieval critical path; Slice D (eval harness) runs in parallel with the tail of Slice C; new C-track tickets (C12-C17) extend Slice C with ingest endpoint + synthetic corpus + frontend.

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
                          Slice C — retrieval + ingest + UI (17 PRs)
                                   │
                          C1..C11  serial retrieval critical path
                                   │
                          C12..C14 ingest endpoint + loaders + synthetic corpus
                                   │       (C12 depends on C9; C14 depends on C12 + C2 + C3)
                                   │
                          C15..C17 frontend (wizard expand + admin ingest + hard-gate modals)
                                   │       (C15 depends on /draft-solicitation/section live = C9;
                                   │        C16 depends on /ingest/document live = C12;
                                   │        C17 is parallel-shippable)
                                   ↓
                          Slice D — eval harness (3 PRs)
                                   │       D1 depends on C1 + C14 (corpus seeded)
                                   │       D2 depends on D1
                                   │       D3 depends on D2
                                   ↓
                          E2E coordinator pass (full-stack smoke; no new PR — verification only)
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

### Slice C extension — ingest endpoint + synthetic corpus + frontend (6 PRs, partially parallel)

Defined in companion specs (`m2-grounded-retrieval/synthetic-corpus.md` for C12-C14, `m2-grounded-retrieval/ui-far-sections.md` for C15-C17). These extend the initial retrieval substrate with admin ingest, the lean synthetic corpus, and the wizard surface.

| # | Branch | Title | Type | Labels | Notes |
|---|---|---|---|---|---|
| **C12** | `cj/m2-c12-ingest-endpoint-and-loaders` | `POST /ingest/document` router + markdown/txt loaders | `feat(ingest):` | — | Depends on C9 (FastAPI wiring conventions). PDF + JSON-prechunked deferred to C13 to keep diff reviewable. Spec: `m2-grounded-retrieval/synthetic-corpus.md` §8 + §9. |
| **C13** | `cj/m2-c13-pdf-json-loaders` | PDF + JSON-prechunked loaders | `feat(ingest):` | — | Adds `pypdf` dep. OCR explicitly out-of-scope. Spec: `m2-grounded-retrieval/synthetic-corpus.md` §9. |
| **C14** | `cj/m2-c14-synthetic-solicitations` | Generate + check-in 10 synthetic solicitations × 2 agencies + `MANIFEST.sha256` | `feat(corpus):` | `far-snapshot-update-approved` extended to synthetic-corpus prefix | Depends on C2 (chunking) + C3 (embeddings) + C12 (ingest endpoint). Lean shape (Parts I+II only) per `m2-grounded-retrieval/synthetic-corpus.md` §3. Synthetic-data CI allowlist expanded to `SOL-GSA-*` / `SOL-DOD-*`. |
| **C15** | `cj/m2-c15-wizard-far-ucf-expand` | Solicitation wizard → 13-step FAR UCF + per-section provenance + section-card component | `feat(ui):` | — | Depends on C9 (`/draft-solicitation/section` live). Provenance state machine per `m2-grounded-retrieval/ui-far-sections.md` §5. Surfaces lean-corpus L/M caveat. |
| **C16** | `cj/m2-c16-admin-ingest-ui` | Admin ingest route + `admin-ingest.component` + `ingest.service.ts` | `feat(ui):` | — | Depends on C12 (`/ingest/document` live). Role guard for admin only. |
| **C17** | `cj/m2-c17-hard-gate-modals` | Publish + amend modal hard-gates citing FAR 5.705 / 15.206 + SSA stub for M3 | `feat(ui):` | — | Parallel-shippable (no dependency on retrieval endpoints). Pure client-side friction; backend HITL middleware arrives with M3. |

### Slice D — eval harness (3 PRs, serial; previously deferred)

Defined in `m2-grounded-retrieval/eval-harness.md`. Runs in parallel with C12-C17 once C14 corpus is seeded.

| # | Branch | Title | Type | Labels | Notes |
|---|---|---|---|---|---|
| **D1** | `cj/m2-d1-eval-set-build` | `eval/build_eval_set.py` + initial `far_eval_set.jsonl` + 6 adversarial cases | `feat(eval):` | — | Depends on C1 (FAR snapshot) + C14 (synthetic-solicitations seeded). 80-120 cases. Adversarial cases authored separately per anti-pattern #9 (ADR-0009 D5). |
| **D2** | `cj/m2-d2-ragas-judge` | `eval/judge.py` (Nova Micro via LiteLLM) + `eval/run_ragas.py` + initial `baseline_main.json` | `feat(eval):` | — | Anti-pattern #1 enforcement: judge != generator. Static CI check that `judge.py` does not import `claude-sonnet`. |
| **D3** | `cj/m2-d3-programmatic-checks` | `eval/run_programmatic.py` (citation validity + cross-tenant fuzz + latency/token) + `ratchet.py` + `.github/workflows/rag-eval-gate.yml` | `feat(eval):` | — | Latency/token tracked NOT gated (REQ-AID-3 scope, PRD §4 AIOps OOS). Required-check name `rag-eval-gate`. |

### Deferred from M2 (kept here for traceability)

These are M2 work but NOT in any of the four slices above:

| Ticket | When | Why deferred |
|---|---|---|
| **M2-10 HITL middleware** | After C9 once `issue_solicitation` tool exists | `/retrieve` endpoint is direct retriever-invoke; no `create_agent` path yet — M3 wiring |
| **M2-11 MongoDBSaver checkpointer** | With M2-10 | Same — only needed when agent + HITL pause is wired |
| **M2-17 Pydantic strict tool-arg** | With M2-10 | Only needed if `@tool`-decorated functions are exposed via agent |
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
| `req_rag_3` marker — cross-tenant impossibility | C4 (locked-passing); C10 adds adversarial cases; D3 adds fuzz | MUST stay green. Equivalent to a debt-style lock in the opposite direction. |
| `verify-bedrock-logging-disabled.sh` | C7 | Asserts Bedrock model invocation logging configuration is disabled |
| `synthetic-data-check.yml` (expanded) | C14 | Allowlist extended to `SOL-GSA-*` + `SOL-DOD-*` synthetic-solicitation prefixes (ADR-0008 D1) |
| `rag-eval-gate.yml` (RAGAS + programmatic checks) | D3 | Faithfulness / Answer Relevancy / Context Precision / Context Recall ratchet vs main + citation validity (hard 1.0) + cross-tenant fuzz (hard 0) + latency/token tracking (soft signal). One-directional threshold ratchet. |

## Estimated rollout shape

24 PRs total to reach end-to-end M2 (retrieval + ingest + frontend + eval):

- 4 pre-tickets (A1, A2, B1, B2) — Slice A + B
- 11 retrieval critical-path tickets (C1..C11) — Slice C core
- 6 extension tickets (C12..C17) — ingest endpoint + synthetic corpus + frontend
- 3 eval tickets (D1..D3) — Slice D

**Critical path:**
- Slices A and B run in parallel → 2 PRs to first merge each.
- Slice C core (C1..C11) is serial → 11 PRs.
- C12..C17 partially parallelize once C9 + C2 are in: C12 → C13 sequential (both ingest); C14 depends on C12; C15 parallel after C9; C16 parallel after C12; C17 parallel from the start.
- Slice D is serial (D1 → D2 → D3) but parallel to C12..C17 once C14 lands.
- Critical-path PR count ≈ 2 (A/B) + 11 (C1..C11) + 2 (C12 → C14) + 3 (D1..D3) = ~18 sequential merges. C13, C15, C16, C17 are parallel-shippable, not adding to the critical path.

Per-PR work is small enough that each lands in a single working session under normal review SLA. Stack of PRs against `main` keeps everyone unblocked except the literal next-up reviewer.

## Sub-agent decomposition for parallel implementation

Once all four specs are merged, kick four implementation tracks in parallel (one sub-agent each, scoped to its spec):

| Agent | Owns | Spec | Tickets |
|---|---|---|---|
| `agent-pipeline` | Backend retrieval stack | `m2-grounded-retrieval/retrieval-pipeline.md` | A1, A2, B1, B2, C1..C11 |
| `agent-corpus` | Synthetic corpus + admin ingest endpoint internals | `m2-grounded-retrieval/synthetic-corpus.md` | C12, C13, C14 |
| `agent-ui` | Wizard expansion + admin ingest UI + hard-gate modals | `m2-grounded-retrieval/ui-far-sections.md` | C15, C16, C17 |
| `agent-eval` | RAGAS + Nova-Micro judge + programmatic checks | `m2-grounded-retrieval/eval-harness.md` | D1, D2, D3 |

After all four merge to `main`, an **e2e coordinator** (separate agent — does NOT implement, only verifies) boots the full docker-compose stack and runs `tests/e2e/test_m2_smoke.py`:

1. Admin uploads a synthetic-solicitation MD via `/admin/ingest` → assert chunks_inserted > 0, no flagged_chunks.
2. Wizard opens, picks Section C → calls `POST /draft-solicitation/section` → assert response has `section_text`, citations[], `gate_decision`, `request_id`.
3. Cross-tenant adversarial fuzz: same query against tenant-A vs tenant-B → assert no chunk_id overlap in citations.
4. Audit-log query by `request_id` → assert record exists with correct schema_version=1 + tenant_id + citations.
5. Eval gate dry-run on a 5-case subset of the eval set → assert all four RAGAS metrics > threshold.

Coordinator is the trust-but-verify step on top of the four parallel agents' work.

## What this spec does NOT cover

- M3 (Agentic source-selection workflow) — separate PRD milestone. C17 leaves UI stubs but no agent wiring.
- Phase 2 modernization items (SB→4.0.x, Java 21, circuit breaker, OTel rollout). PRD §4 OOS.
- Other brownfield-debt item flips beyond Item 5 — those have their own scheduled weeks per `docs/brownfield-debt.md`.
- Cloud-Atlas migration (M2-21 / Phase 1.5 trigger).
- Implementer-grade detail — that lives in the companion specs (`m2-grounded-retrieval/retrieval-pipeline.md`, `m2-grounded-retrieval/synthetic-corpus.md`, `m2-grounded-retrieval/ui-far-sections.md`, `m2-grounded-retrieval/eval-harness.md`). This spec is the PR-ordered + dependency graph; companions are the *how*.

## When to update this spec

- **Before opening A1**: confirm the Item 5 lockfile diff shape against the actual `docs/debt-lockfile.yml` (this spec assumes the flow described in CLAUDE.md; verify the lockfile field names match).
- **After each PR merges**: tick the ticket off; note any deviation from the planned shape so the next planning session can learn.
- **If a C-ticket discovers a missing dependency**: re-thread the order here, not in scattered comments.
