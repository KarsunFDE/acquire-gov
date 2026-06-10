# ai-orchestrator

Python 3.11 + FastAPI + LangChain v1.0+ + Pydantic v2 + boto3.

LLM / RAG / agent orchestration. The legacy `/draft-solicitation` endpoint
is the brownfield-debt stub (Item 4, deliberate). The M2 grounded path
under `/retrieve` and `/draft-solicitation/section` is real — hybrid
retrieval, rerank gate, citation hard-fail, audit log v1.

## M2 prereqs

The grounded-retrieval slice (Slice C; `docs/specs/m2-grounded-retrieval/retrieval-pipeline.md`)
expects the following before `/retrieve` and `/draft-solicitation/section`
return non-stub results:

- **Atlas-local 8.0.8** running via `docker-compose -f infra/docker/docker-compose.yml up`. Hybrid `$rankFusion` requires this version + `?directConnection=true` on `MONGO_URI` (ADR-0005 D3). The container provisions `far_vector_idx` + `far_search_idx` plus the `auditLogWriter` / `auditLogReader` roles via the seed-time DDL runner.
- **Bedrock bearer token** in repo-root `.env`:
  ```bash
  AWS_BEARER_TOKEN_BEDROCK=<token>
  AWS_REGION=us-east-1
  BEDROCK_RERANK_REGION=us-west-2   # Rerank 1.0 is us-west-2 only
  ```
  IAM access-key/secret still works as a fallback. Stub fallback kicks in when no creds are present; first-day learners rely on this.
- **Synthetic-data CI guard** + **FAR snapshot manifest** workflow — `eval/` runs `verify_far_manifest.py` on every PR (`docs/specs/m2-grounded-retrieval/synthetic-corpus.md`). The repo ships synthetic-only content; the guard fails the build if any real PII or non-synthetic identifier appears in `data/`.
- `make seed` runs FAR Part 15.2 + Part 52 ingest plus 10 synthetic solicitations into atlas-local. Idempotent — re-running is safe.

**Not a prereq:** host-disk encryption (BitLocker / FileVault / LUKS) — Phase 2 (PRD §4 OOS, ADR-0008 D1). Synthetic-only corpus + FedRAMP-safe deploy boundary mean disk encryption is Phase-2 territory.

## Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET    | `/health` | (⚠ always 200 — no real dep check) |
| POST   | `/retrieve` | M2 grounded retrieval; hybrid + rerank + gate; per-tenant rate-limit; `X-Tenant-ID` required |
| POST   | `/draft-solicitation/section` | M2 grounded drafting; retrieves + generates + verifies citations; FAR-UCF section `A..H,J..M` |
| POST   | `/ingest/document` | Admin ingest; `md`/`txt`/`pdf`/`json-prechunked` |
| POST   | `/draft-solicitation` | ⚠ Item 4 brownfield stub — raw dict, sometimes `{"clause_id": null}` |
| POST   | `/draft-amendment` | ⚠ Item 4 brownfield stub |
| POST   | `/answer-qa` | ⚠ Items 4 + 9 brownfield stub |
| POST   | `/rag/clause-search` | ⚠ Items 4 + 6 + 7 brownfield stub |
| POST   | `/eval/factor-suggest` | ⚠ Item 4 brownfield stub |
| POST   | `/eval/ssdd-draft` | ⚠ Item 4 brownfield stub |
| POST   | `/agent/intake-triage` | ⚠ Items 4 + 6 brownfield stub |

The brownfield endpoints are deliberate and **must not** be deleted or
modernized outside their scheduled cohort week. See `CLAUDE.md` and
`docs/brownfield-debt.md`.

## Build + run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Spec-driven seed (M2):

```bash
make seed   # FAR Parts 15.2 + 52 + 10 synthetic solicitations → atlas-local
```

## Brownfield-debt items present in this service

- **Item 4** — `/draft-solicitation` returns raw stub JSON; no Pydantic
  response model; 1-in-3 returns `{"clause_id": null}` to exercise the
  downstream NPE.
- **Item 5** — MODERNIZED W2-Mon (PR A1). `app/legacy_chain.py` deleted;
  LLMChain references removed. Sequential prompt flows use plain Python
  (`invoke_model(prompt.format(...))`); agentic flows will use
  `create_agent(model, tools, middleware=[...])` from `langchain.agents`
  when wired in M3. Locked-failing test transitioned to passing;
  `docs/debt-lockfile.yml` flipped `locked: true → false`.
- **Item 6 (partial)** — No correlation-ID logging (the other three services
  each use a different key; this one has none).
- **Item 7** — `pinecone-client` in `requirements.txt`, no `import pinecone`
  anywhere.
- **Item 11 (partial)** — `Dockerfile` was originally `FROM python:latest`; pinned to `python:3.11-slim` in 2026-Q1 after numpy/pydantic-core wheels broke on 3.14. The OTHER 4 Dockerfiles (api-gateway, solicitation-service, evaluation-service, frontend) still carry `:latest`. Cohort finds those.

See `docs/brownfield-debt.md` for the full inventory.
