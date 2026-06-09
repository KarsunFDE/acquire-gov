# Mongo 7 → Atlas Local 8.0.8 migration

**Status:** dev/fresh-start environments do NOT need to run this. M2 is the
first milestone that puts real data in Mongo; before B1 the `mongo:7` image
held only seed scaffolding the cohort generated on-demand. The container
was destroyed and recreated regularly; volume contents were never
load-bearing.

**This note exists** so operators with a hot `mongo-data` volume from a
mongo:7 container (e.g. a long-running dev box, a demo recording rig) can
follow a documented dump → restore step before pulling B1.

## Why a swap is required (and not a volume reuse)

Atlas-local 8.0.8 storage engine + on-disk format are NOT documented as
forward-compatible with `mongo:7` data files (ADR-0005 D3). Reusing the
old `mongo-data` volume against the new image is unsupported and
silently risks corruption.

## Dev migration steps (only if you have data worth keeping)

```bash
# 1. Confirm the stack is up with the OLD mongo:7 image (pre-B1).
docker-compose -f infra/docker/docker-compose.yml ps mongodb

# 2. Dump the existing acquire_gov DB into a host-side artifact.
docker-compose -f infra/docker/docker-compose.yml exec mongodb \
  mongodump --username app --password app_dev_password \
    --authenticationDatabase admin \
    --db acquire_gov \
    --out /data/db/dump-pre-atlas

docker cp \
  $(docker-compose -f infra/docker/docker-compose.yml ps -q mongodb):/data/db/dump-pre-atlas \
  ./dump-pre-atlas

# 3. Stop the stack + DROP the mongo volume.
docker-compose -f infra/docker/docker-compose.yml down
docker volume rm $(docker volume ls -q | grep mongo-data)

# 4. Pull B1 (this commit) onto the branch.
git pull

# 5. Bring up the stack with the new atlas-local 8.0.8 image.
docker-compose -f infra/docker/docker-compose.yml up -d mongodb

# 6. Wait ~30s for atlas-local to finish first-boot init + run seed/.
docker-compose -f infra/docker/docker-compose.yml logs -f mongodb
# (look for "createSearchIndex" lines from infra/mongo/seed/01-indexes.js)

# 7. Restore.
docker cp ./dump-pre-atlas \
  $(docker-compose -f infra/docker/docker-compose.yml ps -q mongodb):/tmp/dump

docker-compose -f infra/docker/docker-compose.yml exec mongodb \
  mongorestore --username app --password app_dev_password \
    --authenticationDatabase admin \
    --nsInclude "acquire_gov.*" \
    --drop \
    /tmp/dump
```

## Smoke verification

```bash
docker-compose -f infra/docker/docker-compose.yml exec mongodb \
  mongosh "mongodb://app:app_dev_password@mongodb:27017/?directConnection=true" \
  --eval 'db.runCommand({buildInfo:1}).version'
# expect: "8.0.8"

docker-compose -f infra/docker/docker-compose.yml exec mongodb \
  mongosh "mongodb://app:app_dev_password@mongodb:27017/?directConnection=true" \
  --eval 'db.getSiblingDB("acquire_gov").chunks.getSearchIndexes()'
# expect: far_vector_idx + far_search_idx, status: READY (or BUILDING for ~1m)
```

## What NOT to do

- Do NOT skip the volume drop. Reusing the mongo:7 volume against
  atlas-local is unsupported per ADR-0005 D3.
- Do NOT seed-import without `--drop` if the target DB has stale data;
  search indexes will pick up duplicate chunks and rerank quality drops.
- Do NOT enable Bedrock model invocation logging during seed. See
  `.github/scripts/verify-bedrock-logging-disabled.sh` (lands C7).
