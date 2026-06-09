# Mongo seed DDL (atlas-local 8.0.8)

Three idempotent JavaScript files mounted into `mongodb-atlas-local`'s
`/docker-entrypoint-initdb.d/` directory. atlas-local runs them via
`mongosh` on first container boot (after the volume initializes); they
no-op on subsequent boots.

| File | Owns | ADR |
|---|---|---|
| `01-indexes.js` | `far_vector_idx` (Titan v2 @ 512) + `far_search_idx` (BM25) on `acquire_gov.chunks` | ADR-0007 D4, ADR-0010 D5 |
| `02-roles.js` | `auditLogWriter` (insert+find) + `auditLogReader` (find) roles | ADR-0008 D3 |
| `03-audit-indexes.js` | `{ts:1}`, `{tenant_id:1, ts:-1}`, `{request_id:1}` indexes on `audit_log` | ADR-0008 D3, ADR-0010 D5 |

## How they get invoked

`infra/docker/docker-compose.yml` mounts this directory read-only into the
mongo container:

```yaml
volumes:
  - ../mongo/seed:/docker-entrypoint-initdb.d:ro
```

## Idempotency

All three scripts swallow "already exists" errors so a `docker-compose up`
against a non-empty volume is a no-op. **Do not run them manually unless
the container is freshly initialized** — they trust the atlas-local
init-script lifecycle for ordering (numeric prefix = run order).

## Verifying

```bash
docker-compose -f infra/docker/docker-compose.yml exec mongodb \
  mongosh "mongodb://app:app_dev_password@mongodb:27017/?directConnection=true" \
  --eval 'db.getSiblingDB("acquire_gov").chunks.getSearchIndexes()'
```

Both `far_vector_idx` and `far_search_idx` should appear with
`status: "READY"` after ~30-60s of background build time.

## What lives elsewhere

- **Chunk content + embedding writes**: Slice C (C2 splitter, C3 embed).
- **audit_log record writer**: `services/ai-orchestrator/app/audit.py` (C7).
- **Service-user binding to auditLogWriter**: ops-side step, NOT a seed
  script (each environment configures its own service user).
