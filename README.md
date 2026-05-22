# `acquire-gov` — Federal Acquisitions Training Project

> **Karsun-FDE 6-week intensive — Cohort #1 brownfield training repo.**
>
> Mirrors how Karsun's federal-acquisitions engagements actually deploy
> (Angular SPA → Spring Boot microservices → Python/FastAPI AI orchestration
> on AWS Bedrock + MongoDB Atlas + PostgreSQL) and is **deliberately imperfect**
> so the cohort has real brownfield debt to inventory (W1 Tue) and modernise
> (W4 Mon–Thu).

## Architecture

```
                  ┌──────────────────────┐
                  │  Angular SPA         │   ← contracting-officer UX surface
                  │  (frontend/)         │      :4200
                  └──────────┬───────────┘
                             │ HTTPS (REST + SSE)
                  ┌──────────▼───────────┐
                  │  API Gateway         │   ← routes + auth-edge
                  │  (api-gateway/)      │      :8080
                  └──┬───────────┬──┬────┘
                     │           │  │ traceparent
        ┌────────────▼──┐  ┌─────▼──▼─────────┐
        │ Solicitation   │  │ Evaluation       │   ← Spring Boot 3.x
        │ Service        │  │ Service          │
        │ (Java) :8081   │  │ (Java) :8082     │
        └────┬───────┬───┘  └────┬─────┬───────┘
             │       │           │     │
             │       └─sync REST─┤     │
             │                   │     │
             │   ┌───────────────▼─────▼───┐
             │   │ AI Orchestrator         │   ← Python/FastAPI
             │   │ (ai-orchestrator/) :8000│      LangChain v1.0 + Pydantic v2
             │   └────┬────────────────┬───┘
             │        │                │
   ┌─────────▼─────┐  │     ┌──────────▼─────┐
   │ PostgreSQL    │  │     │ AWS Bedrock    │   ← LLM provider
   │ :5432         │  │     │ (Claude)       │
   └───────────────┘  │     └────────────────┘
                      │
                ┌─────▼──────────────────┐
                │ MongoDB                │   ← documents +
                │ :27017                 │      Atlas Vector Search (W2)
                └────────────────────────┘
```

## Service inventory

| Path | Service | Tech | Port |
|------|---------|------|------|
| `frontend/` | Angular SPA | Angular 17+ | 4200 |
| `services/api-gateway/` | Auth edge + routing | Spring Boot 3.2 + Spring Cloud Gateway + OAuth2 Resource Server | 8080 |
| `services/solicitation-service/` | FAR/DFARS solicitation CRUD | Spring Boot 3.2 + JPA (Postgres) + MongoDB | 8081 |
| `services/evaluation-service/` | Evaluation panel coordination | Spring Boot 3.2 | 8082 |
| `services/ai-orchestrator/` | LLM/RAG/agent orchestration | Python 3.11 + FastAPI + LangChain v1.0 + Pydantic v2 + boto3 | 8000 |
| `infra/docker/` | Local dev compose stack | Docker Compose | — |
| `infra/github-actions/` | CI/CD workflows | GHA | — |

## Quick start (cohort Day 1)

```bash
# 1. Clone
git clone https://github.com/KarsunFDE/acquire-gov.git
cd acquire-gov

# 2. Copy env template
cp .env.example .env
# (fill in AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY if exercising the Bedrock stub)

# 3. Start the stack
cd infra/docker
docker-compose up --build

# 4. Verify
curl http://localhost:8080/actuator/health        # api-gateway
curl http://localhost:8081/actuator/health        # solicitation-service
curl http://localhost:8082/actuator/health        # evaluation-service
curl http://localhost:8000/health                  # ai-orchestrator
open  http://localhost:4200                       # Angular SPA
```

## Brownfield debt — read this before "fixing" anything

This scaffold has **12 deliberate brownfield-debt items** that the cohort
identifies in `weeks/W01/brownfield-debt.md` on W1 Tue and modernises in
W4 Mon–Thu. **Do not "fix" these before the cohort sees them.**

See `docs/brownfield-debt.md` for the full inventory + which week each item
surfaces. Short list:

1. JWT signature-skip on `/api/public/*` in api-gateway
2. Audit-log written *after* response in solicitation-service (race on crash)
3. No circuit breaker in evaluation-service → solicitation-service
4. No structured-output validation in ai-orchestrator (Bedrock raw passthrough)
5. Pre-v1.0 LangChain `LLMChain(...).run(...)` pattern alongside v1.0 patterns
6. Inconsistent correlation-IDs across services (`X-Request-ID` / `correlationId` / `traceId` / absent)
7. `pinecone-client` listed in `requirements.txt` but never imported
8. Frontend `SolicitationListComponent` hardcodes `http://localhost:8081/api/solicitations` (bypasses gateway)
9. No OWASP input sanitization on solicitation `description` (accepts raw HTML)
10. No multi-tenant boundary — `agency_id` in schema but no query filter
11. Dockerfiles use `:latest` base-image tags
12. GHA `ci.yml` has `# TODO: re-enable lint when we have time` (linting commented out)

Plus reinforcement gaps: no Postgres volume mount in `docker-compose.yml`; no
service healthchecks; OIDC-to-AWS deploy stub never actually deploys.

## How the cohort uses this

| Week | Activity |
|------|----------|
| W1 Mon | Clone, build, run. Each learner picks their weakest sub-stack and onboards with Claude Code. |
| W1 Tue | Microservices walkthrough; **brownfield-debt inventory** captured in `weeks/W01/brownfield-debt.md`. |
| W1 Thu–Fri | First LLM PRs land in `services/ai-orchestrator/` against the solicitation-drafting endpoint. |
| W2 | Hybrid RAG over FAR/DFARS clause library via Atlas Vector Search. **Pre-v1.0 LangChain migrated to v1.0.** |
| W3 | Single + multi-agent (LangGraph) in ai-orchestrator. HITL interrupt nodes added. |
| W4 | Brownfield modernization pass: cohort fixes 2-3 items from the brownfield-debt inventory; AI Security Engineering Wed addresses items 1, 9, 10, 11. |
| W5 | OpenTelemetry instrumentation, AIOps incident drill, governance docs. Fixes correlation-id consistency (item 6). |
| W6 | Training project pauses — pairs focus on their own Pair Projects for client deliverability. |

## Subdirectories

- `services/` — Spring Boot microservices + Python AI orchestrator (each with its own README, Dockerfile, dependency manifest).
- `frontend/` — Angular SPA.
- `infra/docker/` — `docker-compose.yml` + per-service Dockerfiles.
- `infra/github-actions/` — CI/CD workflows.
- `scripts/` — local-dev helpers (seed data, Atlas index bootstrap).
- `docs/` — architecture docs, ADRs, brownfield-debt inventory.

---

Programme spec lives in the team's `fde-10-week/` workspace
(`training-project/README.md` is the design source-of-truth; this repo is
the **code home** the cohort clones).
