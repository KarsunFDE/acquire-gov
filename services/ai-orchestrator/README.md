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
| POST   | `/draft-solicitation-v1` | v1.0 composed-Runnable scaffold (Item 5 modernization target) |

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
- **Item 5** — `app/legacy_chain.py` uses pre-v1.0 `LLMChain(...).run(...)`;
  `app/main.py` uses v1.0 composed-Runnable. Cohort consolidates in W2.
- **Item 6 (partial)** — No correlation-ID logging (the other three services
  each use a different key; this one has none).
- **Item 7** — `pinecone-client` in `requirements.txt`, no `import pinecone`
  anywhere.
- **Item 11** — `Dockerfile` uses `FROM python:latest`.

See `docs/brownfield-debt.md` for the full inventory.
