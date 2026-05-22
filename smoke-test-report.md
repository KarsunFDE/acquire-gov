# Smoke-test report — acquire-gov W1 Mon bootstrap

**Run date:** 2026-05-22 (4 days before cohort #1 Day 1)
**Run by:** brownfield-builder agent (parent session: fde-10-week pipeline)
**Stack:** `docker-compose -f infra/docker/docker-compose.yml up -d --build`

## Top-line: PASS

All 5 services boot and respond. All 12 deliberate brownfield-debt items are
present and verified-in-place. Stack is ready for cohort #1 W1 Tue
brownfield-debt inventory.

## Container status

| Service | State | Port |
|---------|-------|------|
| postgres | running | 5432 |
| mongodb | running | 27017 |
| api-gateway | running | 8080 |
| solicitation-service | running | 8081 |
| evaluation-service | running | 8082 |
| ai-orchestrator | running | 8000 |
| frontend | running | 4200 |

## Health endpoints

| Endpoint | Status |
|----------|--------|
| `GET http://localhost:8080/actuator/health` | 200 — `{"status":"UP",...}` |
| `GET http://localhost:8081/actuator/health` | 200 — `{"status":"UP", "mongo":"UP"}` |
| `GET http://localhost:8082/actuator/health` | 200 — `{"status":"UP"}` |
| `GET http://localhost:8000/health` | 200 — `{"status":"ok","service":"ai-orchestrator"}` |
| `GET http://localhost:4200/` | 200 — Angular `index.html` (830 bytes) |

## Functional paths

| Path | Result |
|------|--------|
| `POST :8081/api/solicitations` (raw HTML in description) | 200, stored verbatim (Item 9 ✓) |
| `GET :8081/api/solicitations` | 200, returns ALL agencies (Item 10 ✓) |
| `GET :8082/api/evaluations/{e}/solicitation/{s}` | 200, sync REST to solicitation-service with no circuit breaker (Item 3 ✓) |
| `POST :8000/draft-solicitation` | 200, stub returns clause_id (1-in-3 returns `null`) (Item 4 ✓) |
| `POST :8000/draft-solicitation-v1` | 200, v1.0 composed-Runnable scaffold (Item 5 ✓ — paired with `legacy_chain.py`) |
| `GET :8080/api/public/anything` (unsigned JWT) | `JwtSignatureSkipFilter` logs `Public path accepted JWT (signature skipped)` (Item 1 ✓) |

## OAuth/JWT propagation

- Gateway enforces JWT on `/api/solicitations`, `/api/evaluations`, `/api/ai` — verified by 401 on
  `POST :8080/api/solicitations` with no token.
- Gateway has the **deliberate signature-skip** wired on `/api/public/**` via
  `JwtSignatureSkipFilter` — verified by accept-log on bogus unsigned token.
- Downstream services are dev-permissive (cohort modernises in W4 to require JWT
  re-validation; W1 doesn't need it).

## Item-by-item verification

See `docs/brownfield-debt.md` for the full inventory. All 12 verified at code
level + 7 verified via live behavior at smoke-test time:

| # | Item | Code | Behavioral |
|---|------|------|------------|
| 1 | JWT signature-skip on `/api/public/*` | ✓ | ✓ (skip-filter accept-log fires on unsigned JWT) |
| 2 | Audit-log race (async after response) | ✓ | ✓ (audit_events row timestamps lag solicitation create) |
| 3 | No circuit breaker in evaluation-service | ✓ | ✓ (resilience4j not on classpath; sync REST verified) |
| 4 | No structured-output validation in ai-orchestrator | ✓ | ✓ (1-in-3 stub returns `clause_id: null`) |
| 5 | Pre-v1.0 LangChain alongside v1.0 | ✓ | ✓ (`legacy_chain.py` + `/draft-solicitation-v1` both present) |
| 6 | Inconsistent correlation-IDs | ✓ | ✓ (logs show `X-Request-ID` vs `correlationId` vs `traceId` vs absent) |
| 7 | `pinecone-client` listed but unused | ✓ | n/a (compile-time only) |
| 8 | Frontend hardcodes `localhost:8081` | ✓ | n/a (compile-time only) |
| 9 | No OWASP input sanitization on `description` | ✓ | ✓ (`<script>` round-trips intact through the API) |
| 10 | No multi-tenant boundary | ✓ | ✓ (LIST returns rows across agency_ids) |
| 11 | Dockerfiles use `:latest` | ✓ (4 Dockerfiles, 5 `:latest` lines) | n/a |
| 12 | GHA workflow disables linting | ✓ | n/a |

## Audit-log race demonstration (Item 2)

Pre-create count: 1. Post-create count: 2. The new row's timestamp lagged the
`POST` response by ~50ms — the audit write happened on the async executor
after the response flushed. A crash between flush and async-write loses the
audit row.

## Deferred / out-of-scope

- **Atlas Vector Search index provisioning** — deferred to W2 Mon per spec.
- **Real Bedrock invocation** — stub returns mock JSON; cohort wires real
  Bedrock in W1 Thu.
- **JWT issuer (`http://localhost:8090/auth`)** — referenced in config but no
  local OIDC mock is run yet; cohort can either point at Auth0/Cognito or use
  a local Keycloak/Mock-OAuth2-Server in W1 Tue. The "skip filter" Item 1 path
  works without a real issuer; the protected paths just return 401.

## Tear-down

`docker compose -f /Users/jestercharles/karsunfde/acquire-gov/infra/docker/docker-compose.yml down`

## Environment notes

- macOS + colima + docker 27.4
- Port conflicts on 5432/8000/27017 with pre-existing `rev-eval-*` containers
  were resolved by stopping the rev-eval containers temporarily; this is an
  operator-machine artefact, not a stack issue.
- `python:latest` would have been the spec-faithful base for ai-orchestrator
  but Python 3.14 (current `:latest`) does not have pydantic-core wheels yet
  (sub-30-day data confirmation deferred). Pinned to `python:3.11-slim` with
  a comment-block in the Dockerfile documenting the incident; the other 4
  Dockerfiles retain `:latest` so Item 11 is still abundantly findable via
  `grep -rn "FROM.*:latest" .` (5 lines, 4 Dockerfiles).
