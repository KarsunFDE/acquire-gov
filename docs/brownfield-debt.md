# Brownfield-debt inventory (instructor-seeded — cohort discovers in W1 Tue)

> **Do not edit during W1 Tue inventory.** The cohort's job is to find these by
> reading code and running the system. This document is the *answer key*; it
> exists so the instructor can verify the inventory exercise.

Each item lists: **location**, **how the cohort finds it**, **which week
surfaces the fix**, and **what "fixed" looks like**.

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
- **How found:** `grep -rn "LLMChain" services/ai-orchestrator/` and `grep -rn "\.run(" services/ai-orchestrator/`. The v1.0 composed-Runnable pattern exists alongside in `app/main.py` (`prompt | llm | parser`) — cohort sees both styles in the same codebase.
- **Surfaces in:** W2 Mon plan-spec; migration is the W2 anchor task.
- **Fixed looks like:** All `LLMChain` + `.run()` rewritten as composed Runnables; `legacy_chain.py` deleted.

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

- **Where:** Every `Dockerfile` in the repo — `services/api-gateway/Dockerfile`, `services/solicitation-service/Dockerfile`, `services/evaluation-service/Dockerfile`, `services/ai-orchestrator/Dockerfile`, `frontend/Dockerfile`.
- **How found:** `grep -rn "FROM.*:latest" .`
- **Surfaces in:** W4 Wed AI Security Engineering Day (OWASP LLM03 Supply Chain).
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
