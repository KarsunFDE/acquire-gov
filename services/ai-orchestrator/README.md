# ai-orchestrator

Python 3.11 + FastAPI + LangChain v1.0+ + Pydantic v2 + boto3.

LLM / RAG / agent orchestration. Currently a Bedrock invocation **stub** —
returns mock JSON for cohort plumbing exercises; the W1 Thu cohort work
wires up real Bedrock calls.

## Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET    | `/health` | (⚠ always 200 — no real dep check) |
| POST   | `/draft-solicitation` | Bedrock stub; ⚠ Item 4 — returns raw JSON, sometimes `{"clause_id": null}` |

## Build + run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
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
