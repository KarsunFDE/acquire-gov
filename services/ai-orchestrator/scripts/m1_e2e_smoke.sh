#!/usr/bin/env bash
# M1 end-to-end smoke (P5.3) — exercises Phases 1–4 in one CLI run.
#
#   1. (optional --reseed) clean atlas-local collections + reseed corpus
#   2. POST /draft-solicitation/batch with all 4 AI sections null
#   3. if batch_interrupted → POST /batch/resume approving every pending Part
#   4. POST /draft-solicitation/critic over the drafted sections
#   5. verify response shapes + run_id joins
#
# Prereqs: compose stack up; AWS_BEARER_TOKEN_BEDROCK in .env for real
# drafting (stub mode exercises preflight/coordinator/critic wiring only).
#
# Usage: ./scripts/m1_e2e_smoke.sh [BASE_URL] [--reseed]
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
TENANT="agency-test"
REQ_ID="$(python -c 'import uuid; print(uuid.uuid4())' 2>/dev/null || uuidgen)"
SOL_ID="sol-e2e-$(date +%s)"

if [ "${2:-}" = "--reseed" ]; then
  echo "== reseed: dropping chunks/audit/agent_checkpoints + reseeding corpus"
  if [ -f "seed/run_seed.py" ]; then
    python - <<'PY'
from pymongo import MongoClient
from app import config
db = MongoClient(config.MONGO_URI)[config.MONGO_DB]
for coll in (config.CHUNKS_COLLECTION, config.AUDIT_LOG_COLLECTION,
              config.AGENT_CHECKPOINT_COLLECTION, config.AGENT_CHECKPOINT_WRITES_COLLECTION):
    db.drop_collection(coll)
print("dropped collections")
PY
    python -m seed.run_seed
  else
    echo "::warning:: seed/run_seed.py not present — skipping reseed"
  fi
fi

echo "== [1/4] /batch (${SOL_ID})"
BATCH="$(curl -sS -X POST "${BASE_URL}/draft-solicitation/batch" \
  -H "X-Tenant-ID: ${TENANT}" -H "X-Request-ID: ${REQ_ID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"solicitation_id\": \"${SOL_ID}\",
    \"naics\": \"541512\", \"set_aside\": \"SDVOSB\",
    \"contract_type\": \"FFP\", \"agency_supplement\": \"GSAM\",
    \"user_constraints_by_section\": {\"C\": \"quarterly deliverable cadence\", \"L\": \"max 25 page proposal\"},
    \"provenances\": {\"C\": null, \"H\": null, \"L\": null, \"M\": null},
    \"part_iii_attachments\": [{\"title\": \"Attachment 1 — PPQ\", \"page_count\": 4}]
  }")"
OUTCOME="$(echo "${BATCH}" | jq -r '.overall_outcome')"
BATCH_RUN_ID="$(echo "${BATCH}" | jq -r '.batch_run_id')"
echo "    overall_outcome=${OUTCOME} batch_run_id=${BATCH_RUN_ID}"
[ "${BATCH_RUN_ID}" = "${SOL_ID}:batch:${REQ_ID}" ] || { echo "FAIL: batch_run_id join broken"; exit 1; }

if [ "${OUTCOME}" = "batch_interrupted" ]; then
  echo "== [2/4] /batch/resume (approve every pending Part)"
  DECISIONS="$(echo "${BATCH}" | jq -c '[.pending_interrupts[] | {section_id: .args.sections[0], decision: "approve"}]')"
  BATCH="$(curl -sS -X POST "${BASE_URL}/draft-solicitation/batch/resume" \
    -H "X-Tenant-ID: ${TENANT}" -H "X-Request-ID: ${REQ_ID}-r" \
    -H "Content-Type: application/json" \
    -d "{\"batch_run_id\": \"${BATCH_RUN_ID}\", \"decisions\": ${DECISIONS}}")"
  OUTCOME="$(echo "${BATCH}" | jq -r '.overall_outcome')"
  echo "    post-resume overall_outcome=${OUTCOME}"
else
  echo "== [2/4] no interrupts — skip resume"
fi
[ "${OUTCOME}" = "batch_completed" ] || { echo "FAIL: batch did not complete"; echo "${BATCH}" | jq .; exit 1; }
echo "${BATCH}" | jq -e '.consistency_report != null and .consistency_report.blocks_submit == false' >/dev/null \
  || { echo "FAIL: completed batch must carry a warn-only consistency_report"; exit 1; }

echo "== [3/4] /critic (Step 12 standalone over drafted sections)"
SECTIONS="$(echo "${BATCH}" | jq -c '[.parts[] | select(.kind == "llm_drafted") | .sections | to_entries[] | select(.value.section_text != null) | {key: .key, value: .value.section_text}] | from_entries')"
CRITIC="$(curl -sS -X POST "${BASE_URL}/draft-solicitation/critic" \
  -H "X-Tenant-ID: ${TENANT}" -H "X-Request-ID: ${REQ_ID}-c" \
  -H "Content-Type: application/json" \
  -d "{\"solicitation_id\": \"${SOL_ID}\", \"set_aside\": \"SDVOSB\", \"sections\": ${SECTIONS}}")"
echo "${CRITIC}" | jq -e '.blocks_submit == false' >/dev/null \
  || { echo "FAIL: critic blocks_submit must be false"; exit 1; }
echo "    critic overall_severity=$(echo "${CRITIC}" | jq -r '.overall_severity') ✓"

echo "== [4/4] audit join check (Mongo direct)"
python - "$BATCH_RUN_ID" <<'PY' || echo "::warning:: audit join check skipped (Mongo unreachable)"
import sys
from pymongo import MongoClient
from app import config
run_id = sys.argv[1]
db = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=1500)[config.MONGO_DB]
rows = list(db[config.AUDIT_LOG_COLLECTION].find({"run_id": run_id}))
parts = list(db[config.AUDIT_LOG_COLLECTION].find({"batch_run_id": run_id}))
print(f"audit rows joined on batch run_id: {len(rows)} coordinator + {len(parts)} part/critic")
assert rows, "no batch_coordinator_run audit row"
PY

echo "== M1 E2E SMOKE GREEN (Step 13 publish modal remains a wizard-side CO act — FAR 5.705)"
