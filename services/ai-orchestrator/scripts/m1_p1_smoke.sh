#!/usr/bin/env bash
# M1 Phase 1 end-to-end smoke (P1.7) - design ref §16 single-section happy path.
#
# Prereqs:
#   - stack up:   docker-compose -f infra/docker/docker-compose.yml up --build
#   - seeded FAR corpus in atlas-local (M2 baseline)
#   - AWS_BEARER_TOKEN_BEDROCK set in .env for the REAL-Bedrock run
#     (without creds the orchestrator returns the deterministic stub draft -
#     still a valid smoke of preflight + retrieval + gate + audit).
#
# Usage: ./scripts/m1_p1_smoke.sh [BASE_URL]
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
TENANT="agency-test"
REQ_ID="$(python -c 'import uuid; print(uuid.uuid4())' 2>/dev/null || uuidgen)"

echo "== M1 P1 smoke → ${BASE_URL} (request_id=${REQ_ID})"

# 1. Happy path - Section C with full Step 1 metadata.
RESP="$(curl -sS -X POST "${BASE_URL}/draft-solicitation/section" \
  -H "X-Tenant-ID: ${TENANT}" -H "X-Request-ID: ${REQ_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "section_id": "C",
    "solicitation_id": "sol-smoke-001",
    "naics": "541512",
    "set_aside": "SDVOSB",
    "contract_type": "FFP",
    "agency_supplement": "GSAM",
    "constraints": "deliverable cadence quarterly"
  }')"

echo "${RESP}" | jq -e '.outcome' >/dev/null || { echo "FAIL: no outcome in response"; echo "${RESP}"; exit 1; }

OUTCOME="$(echo "${RESP}" | jq -r '.outcome')"
echo "   outcome=${OUTCOME}"
case "${OUTCOME}" in
  draft_returned)
    echo "${RESP}" | jq -e '.citations | length > 0' >/dev/null \
      || { echo "FAIL: draft_returned with empty citations"; exit 1; }
    echo "${RESP}" | jq -e '.run_id and .request_id' >/dev/null \
      || { echo "FAIL: missing run_id/request_id"; exit 1; }
    echo "   citations=$(echo "${RESP}" | jq '.citations | length') gate=$(echo "${RESP}" | jq -r '.gate_decision')"
    ;;
  interrupted|withheld)
    echo "   (acceptable non-happy outcome for lean corpus - see Phase 2 for resume)"
    ;;
  *)
    echo "FAIL: unexpected outcome ${OUTCOME}"; exit 1;;
esac

# 2. Preflight rejection - missing contract_type/naics/set_aside must 422.
PF_STATUS="$(curl -sS -o /tmp/m1_p1_preflight.json -w '%{http_code}' \
  -X POST "${BASE_URL}/draft-solicitation/section" \
  -H "X-Tenant-ID: ${TENANT}" -H "X-Request-ID: ${REQ_ID}-pf" \
  -H "Content-Type: application/json" \
  -d '{"section_id": "C", "solicitation_id": "sol-smoke-001"}')"
[ "${PF_STATUS}" = "422" ] || { echo "FAIL: preflight expected 422, got ${PF_STATUS}"; exit 1; }
jq -e '.missing_required | index("contract_type")' /tmp/m1_p1_preflight.json >/dev/null \
  || { echo "FAIL: 422 missing_required lacks contract_type"; exit 1; }
echo "   preflight 422 OK ($(jq -c '.missing_required' /tmp/m1_p1_preflight.json))"

echo "== SMOKE GREEN"
