# DEMO-DAY HANDOFF — acquire-gov AI demo

**Written:** 2026-06-15 (end of session) · **Demo:** next day · **Branch:**
`cj/m1-langchain-integration` (12 commits ahead of `main`; **all this session's
work is UNCOMMITTED**).

Goal for the demo: **full frontend experience** of the AI-assisted solicitation
wizard, end-to-end, with live generations, plus an architecture slide deck
(diagram-heavy, RAG multi-layer emphasis) built in cowork.

Read order for the fresh session: this file → §1 (do-first) → §2 (what's done) →
the deeper handoffs (`handoff.md`, `handoff.md §4.5` critic, M2 `handoff.md`).

---

## 1. ⚠ DO FIRST (demo blockers)

1. **Bedrock key is ROLLED.** Every generation currently returns `503
   bedrock_unavailable`. The whole comms/routing path is proven, but **no real
   drafts until a fresh `AWS_BEARER_TOKEN_BEDROCK` is in the repo-root `.env`**.
   After updating `.env`: `docker-compose -f infra/docker/docker-compose.yml up -d
   --force-recreate ai-orchestrator` (compose `env_file` reads `.env`; `environment:`
   does NOT shadow the AWS creds). Then re-run a smoke (see §3) to confirm a real
   `draft_returned`.
2. **Decide: commit the session's work before the demo.** 25 modified + 6 new
   files, all uncommitted (full list at bottom). For demo stability, commit to
   `cj/m1-langchain-integration`. Suggested logical groups:
   - `fix(m2): wire live retrieval — vector store, index DDL, bulk insert, lc-mongodb>=0.11`
   - `fix(gateway): CORS + OPTIONS permit + StripPrefix + dedupe ACAO for SPA→AI`
   - `fix(m1): Bedrock tool-schema compat (ToolStrategy + sanitizer); critic recursion cap + skipped-caveat`
   - `chore: UTF-8 re-encode clause matrix + smoke scripts; seed_corpus.sh`
   - `docs: AI architecture diagram deck + demo handoff`
3. **Verify corpus is still seeded** (Mongo persists across restarts, vol-mounted):
   `docker exec docker-mongodb-1 mongosh "mongodb://app:app_dev_password@localhost:27017/?directConnection=true" --quiet --eval 'print(db.getSiblingDB("acquire_gov").chunks.countDocuments())'`
   → expect **786** (393 × tenants agency-test + GSA-FAS). If 0, reseed:
   `cd services/ai-orchestrator && bash scripts/seed_corpus.sh`.
4. **Demo entry path:** browser → `http://localhost:4200/` → land on dashboard →
   click **"+ New solicitation"**. Do NOT deep-link `/solicitations/new` — nginx
   has no SPA fallback so deep links 404 (see §4). Role defaults to **Dana Reeves
   (CO, GSA-FAS)** — tenant GSA-FAS, which is seeded.

---

## 2. What this session shipped (all working, all uncommitted)

### 2a. Frontend ↔ AI-orchestrator comms — FIXED (4 stacked bugs)
Browser→gateway→orch was fully broken. Fixes (see [[project_frontend_ai_comms]]):
- Gateway `SecurityConfig.java`: added `.cors()` + `CorsConfigurationSource` bean;
  permit `OPTIONS /**`; **DEMO-ONLY** permit `/api/ai/**` (SPA has no JWT — marked
  REVERT in code).
- Gateway `RouteConfig.java`: `StripPrefix(2)` on the AI route (orch serves at
  root, not under `/api/ai`); `DedupeResponseHeader` for `Access-Control-Allow-Origin`
  (gateway + orch both emit it → browser rejected the duplicate).
- Orch `main.py`: FastAPI `CORSMiddleware` (defense-in-depth / direct + pair-projects).
- **Proven in a real browser** (Playwright): AI call returns `503 acao=:4200`,
  zero CORS errors, zero failed requests. curl could NOT catch the dup-ACAO bug —
  verify CORS in a browser.

### 2b. M1 live-Bedrock wiring — FIXED (M2 "C9" was never actually live)
Prior green was all mocked. Real gaps fixed (see [[project_m1_live_verification]]):
- `MONGO_URI` vs compose `MONGO_URL` mismatch; added `MONGO_URI` + `CLAUSE_MATRIX_PATH`
  to compose, docs volume mount.
- `app/retrieval.py`: implemented `bulk_insert_chunks`, `find_existing_document`,
  real `_get_vector_store` (MongoDBAtlasVectorSearch + Bedrock embeddings),
  `_ChunkDictRetriever` adapter, `ensure_search_indexes` (vector 512-cosine + BM25,
  tenant_id filter). **Ingest was writing 0 chunks before this.**
- `requirements.txt`: `langchain-mongodb>=0.11` (0.7.x breaks under langchain v1),
  pulls `langchain-text-splitters>=1.0`.
- `app/agents/bedrock_schema_compat.py` (NEW): strips JSON-schema keywords Bedrock
  Converse rejects (`minimum`, `prefixItems`, `minItems`>1); installed in
  `app/agents/__init__`. Plus `ToolStrategy(...)` wrap on all 3 agent builders
  (fixes "compiled grammar too large").
- `clause_applicability.json` + smoke scripts re-encoded CP1252→UTF-8 (+ MANIFEST
  hash regenerated).
- **Live smokes GREEN** with a key: p1, p3, batch-critic, e2e (see §3).

### 2c. Critic known-issue — CONTAINED (not fixed)
Nova Lite loops the critic agent forever (one runaway = 2.8M tokens). Bounded by
`CRITIC_RECURSION_LIMIT=3` at both invoke sites; on failure returns a
`critic_skipped=true` / severity=warn report with a "review manually" caveat
(never 500s, never blocks). Wizard Step 12 shows a banner. **Standalone /critic
will always skip** at limit 3 (Nova can't finish in 2 turns); batch critic
sometimes succeeds. Full writeup + real-fix options: `handoff.md §4.5`. For the
demo this is fine — it's warn-only and the caveat reads as intentional rigor.

### 2d. Architecture diagrams — DONE (the deck deliverable)
`docs/diagrams/ai-architecture.md` — 10 Mermaid diagrams, all rendered to
`docs/diagrams/ai-arch-*.png`. Headliners: §3 RAG 4-layer pipeline, §4 agentic
drafting tool sequence. Has mermaid.live + mmdc export instructions and a
suggested slide order. Demo screenshots in `docs/diagrams/shots/`
(`00-dashboard` … `05-review-step12`). Re-capture with real generations:
`cd frontend && node e2e-demo-capture.mjs` (after a fresh key) — note the script
hardcodes an npx-cache playwright path that may need updating.

---

## 3. Verify commands (run after fresh key)

```bash
# health + corpus
curl -s http://localhost:8000/health
# live smokes (stack up + key in .env)
cd services/ai-orchestrator
bash scripts/m1_p1_smoke.sh          # /section happy path → draft_returned + citations
bash scripts/m1_p3_smoke.sh          # /batch fan-out → batch_completed
bash scripts/m1_p4_batch_critic_smoke.sh
MONGO_URI="mongodb://app:app_dev_password@localhost:27017/?directConnection=true" \
  bash scripts/m1_e2e_smoke.sh       # phases 1-4 in one run
# through the GATEWAY (browser path) — should NOT be 404/401/CORS
curl -s -X POST http://localhost:8080/api/ai/draft-solicitation/section \
  -H "Origin: http://localhost:4200" -H "X-Tenant-ID: GSA-FAS" \
  -H "Content-Type: application/json" \
  -d '{"section_id":"C","solicitation_id":"x","naics":"541512","set_aside":"SDVOSB","contract_type":"FFP","agency_supplement":"GSAM","constraints":"quarterly"}'
```
Backend suite: `python -m pytest tests/ -q` → only the 3 locked brownfield-debt
tests fail (expected). `pytest -m req_aid_1` = 4, `pytest -m req_rag_3` = 14.

---

## 4. Known issues / findings (NOT demo blockers, know them)

- **nginx SPA 404:** `frontend/Dockerfile` uses bare `nginx:latest`, no nginx.conf
  → deep links 404. Demo enters via dashboard. Real fix: nginx.conf with
  `try_files $uri /index.html`.
- **Gateway `/api/ai/**` is permitAll (DEMO ONLY)** — no real auth. Marked REVERT
  in `SecurityConfig.java`. Don't present this as the security story.
- **Critic always skips standalone** (see §2c).

## 5. Roadmap items raised (DO NOT build for the demo — talking points only)

Domain-coupling findings worth mentioning as "v2" depth, not gaps:
1. **Sequence the draft DAG.** Batch currently drafts Part I (C,H) and Part IV
   (L,M) as parallel siblings, so **L/M are generated without seeing the drafted
   Section C** (the SOW). FAR: L/M must be written against C (and B's CLINs);
   L↔M alignment is handled (drafted together) but C→L/M is not. Fix later:
   sequence C → L/M (feed drafted C as context). Critic catches some misalignment
   post-hoc but it's warn-only.
2. **Wire template-pull for D–G + K.** These are "agency template + minor
   solicitation-specific edits" (D-G step + Section K both have unwired
   "template-pulled"/"retrieval suggests a template" labels). The `agency_template`
   ingest doc_class already exists; nothing retrieves/merges it. Strong RAG
   candidate (retrieve template → LLM-merge with the rest of the form) — high
   consistency value, low hallucination surface. Deferred in M1 (low narrative).

Full dependency graph + reasoning is in the chat that produced this doc; the short
version: **C is the root**; B,D,E,F,H,L,M all draw from C; A,G,I,J,K are
metadata/programmatic-driven and independent. L/M are leaves (nothing needs them).

---

## 6. Current state snapshot

- All 7 containers up (gateway + orch rebuilt this session; others up 2-4 days).
- Corpus: 786 chunks, tenants `agency-test` + `GSA-FAS`, indexes `far_vector_idx`
  + `far_search_idx` READY.
- Bedrock key ROLLED → generations 503 until replaced.
- Uncommitted: 25 modified, 6 untracked (`docs/diagrams/`,
  `app/agents/bedrock_schema_compat.py`, `scripts/seed_corpus.sh`,
  `frontend/e2e-demo-capture.mjs`, plus session tooling `.agents/`/`.claude/skills/`
  /`.githooks/`/`skills-lock.json` which are NOT demo work — leave them).
- Memory files updated: `project_frontend_ai_comms`, `project_m1_live_verification`.
