#!/usr/bin/env bash
# M1 Phase 3 batch smoke (P3.8) — design ref §18.12.3 per-Part fan-out.
#
# Prereqs: compose stack up + seeded corpus; AWS_BEARER_TOKEN_BEDROCK for
# real-Bedrock Part drafting.
#
# Usage: ./scripts/m1_p3_smoke.sh [BASE_URL]
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
TENANT="agency-test"
REQ_ID="$(python -c 'import uuid; print(uuid.uuid4())' 2>/dev/null || uuidgen)"

echo "== M1 P3 batch smoke → ${BASE_URL} (request_id=${REQ_ID})"

RESP="$(curl -sS -X POST "${BASE_URL}/draft-solicitation/batch" \
  -H "X-Tenant-ID: ${TENANT}" -H "X-Request-ID: ${REQ_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "solicitation_id": "sol-batch-001",
    "naics": "541512",
    "set_aside": "SDVOSB",
    "contract_type": "FFP",
    "agency_supplement": "GSAM",
    "user_constraints_by_section": {
      "C": "quarterly deliverable cadence",
      "L": "max 25 page proposal"
    },
    "provenances": {"C": null, "H": null, "L": null, "M": null},
    "part_iii_attachments": [
      {"title": "Attachment 1 — Past performance questionnaire", "date": "2026-06-10", "page_count": 4, "filename": "att1.pdf"}
    ]
  }')"

OUTCOME="$(echo "${RESP}" | jq -r '.overall_outcome')"
echo "   overall_outcome=${OUTCOME}"

case "${OUTCOME}" in
  batch_completed)
    for kv in "I llm_drafted" "II programmatic_resolved" "III wizard_provided" "IV llm_drafted"; do
      part="${kv%% *}"; kind="${kv##* }"
      actual="$(echo "${RESP}" | jq -r ".parts.\"${part}\".kind")"
      [ "${actual}" = "${kind}" ] || { echo "FAIL: parts.${part}.kind=${actual}, want ${kind}"; exit 1; }
    done
    echo "${RESP}" | jq -e '.parts."II".sections."I".clauses_by_reference | length > 0' >/dev/null \
      || { echo "FAIL: empty Part II clause list"; exit 1; }
    echo "   4 Part kinds OK; Section I clauses resolved"
    ;;
  batch_interrupted)
    BATCH_RUN_ID="$(echo "${RESP}" | jq -r '.batch_run_id')"
    PENDING_N="$(echo "${RESP}" | jq '.pending_interrupts | length')"
    echo "   pending_interrupts=${PENDING_N}; resuming all-approve…"
    SECTION="$(echo "${RESP}" | jq -r '.pending_interrupts[0].args.sections[0]')"
    RESUME="$(curl -sS -X POST "${BASE_URL}/draft-solicitation/batch/resume" \
      -H "X-Tenant-ID: ${TENANT}" -H "X-Request-ID: ${REQ_ID}-r" \
      -H "Content-Type: application/json" \
      -d "{\"batch_run_id\": \"${BATCH_RUN_ID}\", \"decisions\": [{\"section_id\": \"${SECTION}\", \"decision\": \"approve\"}]}")"
    [ "$(echo "${RESUME}" | jq -r '.overall_outcome')" = "batch_completed" ] \
      || { echo "FAIL: resume did not complete: $(echo "${RESUME}" | jq -c '.')"; exit 1; }
    echo "   resume → batch_completed"
    ;;
  *)
    echo "FAIL: unexpected overall_outcome ${OUTCOME}"; echo "${RESP}" | jq '.'; exit 1;;
esac

echo "== P3 SMOKE GREEN"
