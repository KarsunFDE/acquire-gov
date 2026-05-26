# evaluation-service

Spring Boot 2.7.18. Evaluation panel coordination. Calls solicitation-service over sync REST. Java 11 baseline. W4 modernizes to SB 3.x + Java 17.

## Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET    | `/api/evaluations/{evaluationId}/solicitation/{solicitationId}` | Fetches solicitation via solicitation-service |
| POST   | `/api/evaluations` | Create panel (⚠ no idempotency key — Item 3) |

## Brownfield-debt items present in this service

- **Item 3** — No Resilience4j circuit breaker / timeout / fallback on `SolicitationClient`; no idempotency key on `POST /api/evaluations`.
- **Item 6 (partial)** — Logs `traceId` (third correlation-ID convention).
- **Item 11** — `Dockerfile` uses `:latest`.

See `docs/brownfield-debt.md` for the full inventory.
