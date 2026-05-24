# Brownfield-debt inventory (instructor-seeded — cohort discovers in W1 Tue)

> **Do not edit during W1 Tue inventory.** The cohort's job is to find these by
> reading code and running the system. This document is the *answer key*; it
> exists so the instructor can verify the inventory exercise.

Each item lists: **location**, **how the cohort finds it**, **which week
surfaces the fix**, and **what "fixed" looks like**.

---

## Role in D-059 pair-brownfield design — SHARED BASELINE

Per `fde-10-week/pipeline/DECISIONS.md` D-059 (locked 22 May 2026), the 12 items
below are the **shared assessment baseline** across all pair-project brownfields
in a cohort.

When `skills/pair-brownfield-generator/SKILL.md` runs (3× per cohort on W1
Wed PM + Thu), it:

1. Propagates **these 12 baseline items intact** into each pair's renamed
   repo (rubric-parity floor — all 3 pairs start from the same debt shape).
2. Injects **4-6 per-pair-unique items** drawn from
   `fde-10-week/skills/pair-brownfield-generator/references/pair-unique-debt-pool.yml`,
   distinct across pairs (drives real discovery work + W3/W6 cross-pair
   integration learning).
3. Authors a 3-5 item **stretch backlog** in each pair's `BACKLOG.md` from
   `references/stretch-backlog-pool.yml` (aspirational, not assessed).

**For the cohort:** when you open your pair-project repo on W1 Thu morning,
you'll see baseline items below + your pair-unique items in your repo's
`docs/pair-unique-debt.md`. Modernization work across W2–W6 covers BOTH
sets. Different pairs got different unique items — your W3+W6 retro
includes a cross-pair comparison.

**For the instructor:** if any baseline item below is accidentally
"fixed" during reshape, halt the pair-brownfield-generator run. Baseline
parity is assessment-critical.

---

## Item 1 — JWT signature-skip on `/api/public/*`

- **Where:** `services/api-gateway/src/main/java/com/karsunfde/acquiregov/gateway/SecurityConfig.java`
- **How found:** Walkthrough of `SecurityWebFilterChain` reveals `pathMatchers("/api/public/**").permitAll()` *and* a `JwtSignatureSkipFilter` that runs on the public path and accepts unsigned JWTs.
- **Surfaces in:** W1 Tue brownfield-debt inventory; fix lands W4 Wed (AI Security Engineering Day, OWASP LLM07/08 angle).
- **Fixed looks like:** All routes go through the same JWT validation; the skip filter is deleted.

## Item 2 — Audit-log race in solicitation-service

- **Where:** `services/solicitation-service/.../service/SolicitationService.java` + `.../audit/AuditLogger.java`
- **How found:** Crash drill — kill the service mid-CRUD; audit row missing for completed operation.
- **Surfaces in:** W3 multi-agent HITL audit-trail work + W5 Wed AIOps governance.
- **Fixed looks like:** Audit write inside the same `@Transactional` boundary as the CRUD operation; transactional outbox pattern preferred.

## Item 3 — No circuit breaker in evaluation-service → solicitation-service

- **Where:** `services/evaluation-service/.../client/SolicitationClient.java`
- **How found:** Load test the evaluation endpoint while solicitation-service is slow; threads pile up. No `@CircuitBreaker`, no `@TimeLimiter`, no Resilience4j config in `application.yml`.
- **Surfaces in:** W4 Thu reliability engineering.
- **Fixed looks like:** Resilience4j circuit breaker + fallback + timeout; idempotency keys on state-mutating endpoints.

## Item 4 — No structured-output validation in ai-orchestrator

- **Where:** `services/ai-orchestrator/app/main.py` `/draft-solicitation` endpoint
- **How found:** Call the endpoint; downstream Spring service hits a `NullPointerException` when stub returns `{"clause_id": null, ...}`.
- **Surfaces in:** W1 Fri output validation + W2 Mon RAG design.
- **Fixed looks like:** Pydantic `DraftResponse` model with strict-mode validation; Bedrock raw response is parsed + re-emitted through the schema.

## Item 5 — Pre-v1.0 LangChain patterns

- **Where:** `services/ai-orchestrator/app/legacy_chain.py` (uses `LLMChain(...).run(...)`)
- **How found:** `grep -rn "LLMChain" services/ai-orchestrator/` and `grep -rn "\.run(" services/ai-orchestrator/`. The v1.0 pattern exists alongside in `app/main.py` — cohort sees both styles in the same codebase.
- **Surfaces in:** W2 Mon plan-spec; migration is the W2 anchor task.
- **Fixed looks like:** `LLMChain` + `.run()` removed; sequential prompt-flows via plain Python (`model.invoke(prompt.format(...))`); agentic flows via `create_agent(model, tools, middleware=[...])` from `langchain.agents`. `legacy_chain.py` deleted. Per LangChain v1.0 (Oct 2025) — `Chain` class is removed; LCEL `|` pipe is no longer the central composition pattern. Pydantic still standard for structured output + tool args; only `create_agent(state_schema=...)` requires TypedDict.

## Item 6 — Inconsistent correlation-IDs

- **Where:**
  - `api-gateway`: logs `X-Request-ID`
  - `solicitation-service`: logs `correlationId`
  - `evaluation-service`: logs `traceId`
  - `ai-orchestrator`: no correlation-ID logging at all
- **How found:** Tail logs across all services during a single request; the IDs don't line up.
- **Surfaces in:** W1 Tue structured-logging exercise + W5 Tue OTel work.
- **Fixed looks like:** All services emit W3C `traceparent`; OTel context propagation auto-instrumented.

## Item 7 — `pinecone-client` listed but unused

- **Where:** `services/ai-orchestrator/requirements.txt` (line `pinecone-client==5.0.0`)
- **How found:** `grep -r pinecone services/ai-orchestrator/` returns only `requirements.txt`. No `import pinecone` anywhere.
- **Surfaces in:** W2 Mon when Atlas Vector Search work begins.
- **Fixed looks like:** Line removed from `requirements.txt`.

## Item 8 — Frontend hardcodes service URL (bypasses gateway)

- **Where:** `frontend/src/app/components/solicitation-list/solicitation-list.component.ts`
  - `private apiUrl = 'http://localhost:8081/api/solicitations';`
- **How found:** Searching for `http://localhost` in `frontend/src/` returns the hardcode; comparing with the rest of the app (which uses `environment.apiGatewayUrl`).
- **Surfaces in:** W4 Tue API modernization patterns.
- **Fixed looks like:** All API calls route through `environment.apiGatewayUrl` (= `http://localhost:8080`).

## Item 9 — No OWASP input sanitization on solicitation `description`

- **Where:** `services/solicitation-service/.../dto/SolicitationCreateRequest.java` + `.../service/SolicitationService.java`
- **How found:** POST a solicitation with `<script>alert(1)</script>` in the `description` field; it's stored verbatim and returned on GET. No `Jsoup.clean()`, no allow-list, no `@SafeHtml`.
- **Surfaces in:** W4 Wed AI Security Engineering Day (prompt-injection-via-stored-content — solicitation descriptions feed the ai-orchestrator prompt).
- **Fixed looks like:** Jsoup allow-list sanitization on write; output-encoding on read.

## Item 10 — No multi-tenant boundary

- **Where:** `services/solicitation-service/.../model/Solicitation.java` + `.../repository/SolicitationRepository.java`
- **How found:** Schema has `agency_id` field, but `SolicitationRepository.findAll()` returns *all* solicitations across agencies; no `findByAgencyId` in use.
- **Surfaces in:** W2 Wed multi-tenant retrieval-boundary work.
- **Fixed looks like:** Every repository method filters by `agency_id`; tenant context resolved from the JWT.

## Item 11 — Dockerfiles use `:latest`

- **Where:** Most Dockerfiles — `services/api-gateway/Dockerfile`, `services/solicitation-service/Dockerfile`, `services/evaluation-service/Dockerfile`, and `frontend/Dockerfile` (which uses *two* — `node:latest` for build, `nginx:latest` for runtime). `services/ai-orchestrator/Dockerfile` was originally `FROM python:latest` and was hand-pinned to `python:3.11-slim` in 2026-Q1 after numpy/pydantic-core wheels broke on Python 3.14 — the comment block at the top of that Dockerfile documents the incident.
- **How found:** `grep -rn "FROM.*:latest" .` returns 5 lines across 4 Dockerfiles.
- **Surfaces in:** W4 Wed AI Security Engineering Day (OWASP LLM03 Supply Chain).
- **Teaching moment:** The python-pin is itself a teachable artefact — `:latest` *eventually* breaks, and the ai-orchestrator Dockerfile is the receipt. Cohort question: "if the python image had to be pinned to keep the stack building, why are the other four still on `:latest`?"
- **Fixed looks like:** Every base image pinned to a specific tag and SHA256 digest; Renovate/Dependabot configured.

## Item 12 — GHA workflow disables linting

- **Where:** `infra/github-actions/ci.yml`
  - `# TODO: re-enable lint when we have time`
- **How found:** Cohort opens their first PR, notices the `lint` step is skipped in the GHA logs.
- **Surfaces in:** W4 Tue spec-driven-dev when the cohort discovers their own PRs aren't actually linted.
- **Fixed looks like:** Lint step uncommented; ruff (python) + checkstyle (java) + eslint (angular) all run on every PR.

---

## Reinforcement gaps (no separate item number; reinforce the above)

- **No healthchecks in `docker-compose.yml`** — reinforces item 11 (supply-chain hygiene) and item 6 (observability).
- **Postgres data volume NOT mounted** — `mongo-data` IS persisted; the inconsistency itself is a teaching moment (reinforces item 11).
- **OIDC-to-AWS deploy stub never actually deploys** in `infra/github-actions/deploy.yml` — reinforces item 12.

---

*Each item is intentional. If you see code that "looks broken" — verify against this
inventory before "fixing" it.*
