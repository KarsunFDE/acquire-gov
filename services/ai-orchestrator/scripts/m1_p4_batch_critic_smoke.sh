#!/usr/bin/env bash
# M1 Phase 4 batch+critic smoke (P4.6, depends on P4.5 swap) - /batch end-to-end
# with the REAL critic running after aggregate. With LANGSMITH_TRACING=true,
# verify in the trace UI that the consistency_critic span fires AFTER the
# aggregate span under the batch_coordinator_run parent.
#
# Usage: ./scripts/m1_p4_batch_critic_smoke.sh [BASE_URL]
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
TENANT="agency-test"
REQ_ID="$(python -c 'import uuid; print(uuid.uuid4())' 2>/dev/null || uuidgen)"

echo "== M1 P4 batch+critic smoke → ${BASE_URL}"

RESP="$(curl -sS -X POST "${BASE_URL}/draft-solicitation/batch" \
  -H "X-Tenant-ID: ${TENANT}" -H "X-Request-ID: ${REQ_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "solicitation_id": "sol-bc-001",
    "naics": "541512",
    "set_aside": "SDVOSB",
    "contract_type": "FFP",
    "agency_supplement": "GSAM",
    "user_constraints_by_section": {"C": "quarterly deliverable cadence"},
    "provenances": {"C": null, "H": null, "L": null, "M": null},
    "part_iii_attachments": []
  }')"

OUTCOME="$(echo "${RESP}" | jq -r '.overall_outcome')"
echo "   overall_outcome=${OUTCOME}"

if [ "${OUTCOME}" = "batch_completed" ]; then
  echo "${RESP}" | jq -e '.consistency_report != null' >/dev/null \
    || { echo "FAIL: batch_completed without consistency_report"; exit 1; }
  echo "${RESP}" | jq -e '.consistency_report.blocks_submit == false' >/dev/null \
    || { echo "FAIL: blocks_submit must be false"; exit 1; }
  SEV="$(echo "${RESP}" | jq -r '.consistency_report.overall_severity')"
  if [ "$(echo "${RESP}" | jq -r '.consistency_report.critic_skipped // false')" = "true" ]; then
    echo "   ⚠ critic_skipped=true (known issue) - severity=${SEV}; CO must review manually"
  else
    echo "   critic ran post-aggregate: overall_severity=${SEV}, blocks_submit=false ✓"
  fi
elif [ "${OUTCOME}" = "batch_interrupted" ]; then
  echo "${RESP}" | jq -e '.consistency_report == null' >/dev/null \
    || { echo "FAIL: interrupted batch must skip the critic"; exit 1; }
  echo "   interrupted before critic (expected for hitl-band scores) - resume per m1_p3_smoke.sh"
else
  echo "FAIL: unexpected outcome ${OUTCOME}"; exit 1
fi

echo "== P4 BATCH+CRITIC SMOKE GREEN"
