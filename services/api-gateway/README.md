# api-gateway

Spring Boot 3.2 + Spring Cloud Gateway + Spring Security OAuth2 Resource Server.

## Routes

| Path | Forwards to |
|------|-------------|
| `/api/solicitations/**` | solicitation-service:8081 |
| `/api/evaluations/**` | evaluation-service:8082 |
| `/api/ai/**` | ai-orchestrator:8000 |
| `/api/public/**` | solicitation-service:8081 (⚠ signature-skip — Item 1) |

## Build + run

```bash
mvn -B -DskipTests package
java -jar target/api-gateway-*.jar
```

Or via Docker Compose: `cd ../../infra/docker && docker-compose up api-gateway`.

## Brownfield-debt items present in this service

- **Item 1** — JWT signature verification skipped on `/api/public/**`
  (`JwtSignatureSkipFilter.verifySignature` is a no-op).
- **Item 6 (partial)** — Logs correlation as `X-Request-ID` (inconsistent
  with other services).
- **Item 11** — `Dockerfile` uses `:latest` base image.

See `docs/brownfield-debt.md` for the full inventory.
