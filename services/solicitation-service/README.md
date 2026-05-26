# solicitation-service

Spring Boot 2.7.18 + Spring Data MongoDB. FAR/DFARS solicitation CRUD. Java 11 baseline. W4 modernizes to SB 4.0.x + Java 21.

## Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET    | `/api/solicitations` | List all (⚠ no tenant filter — Item 10) |
| GET    | `/api/solicitations/{id}` | |
| POST   | `/api/solicitations` | Create (⚠ no input sanitization — Item 9) |
| PUT    | `/api/solicitations/{id}` | |
| DELETE | `/api/solicitations/{id}` | |

## Build + run

```bash
mvn -B -DskipTests package
java -jar target/solicitation-service-*.jar
```

## Brownfield-debt items present in this service

- **Item 2** — Audit row written async, after HTTP response is flushed (race).
- **Item 6 (partial)** — Logs `correlationId` (not `X-Request-ID` like the gateway).
- **Item 9** — `description` accepts arbitrary HTML.
- **Item 10** — `agency_id` in schema but no query filter.
- **Item 11** — `Dockerfile` uses `:latest`.

See `docs/brownfield-debt.md` for the full inventory.
