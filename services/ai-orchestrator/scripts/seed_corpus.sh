#!/usr/bin/env bash
# Corpus seed via POST /ingest/document - fills the "make seed" gap noted in
# the M2 handoff §6 (seed/run_seed.py's write path is a deliberate no-op;
# the endpoint IS the loader stack, spec §11).
#
# Seeds docs/reference/far/*.md (doc_class=far_reference) and
# docs/reference/synthetic-solicitations/**/*.md (doc_class=synthetic_solicitation)
# under each tenant given (default: agency-test + GSA-FAS - smoke scripts use
# agency-test; the wizard's role defaults send GSA-FAS).
#
# Idempotent: the endpoint 409s on (tenant, source_doc, snapshot_date)
# duplicates; we count those as "skipped".
#
# Usage: ./scripts/seed_corpus.sh [BASE_URL] [TENANT ...]
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
shift || true
TENANTS=("${@:-}")
[ -z "${TENANTS[0]:-}" ] && TENANTS=("agency-test" "GSA-FAS")

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SNAPSHOT_DATE="2026-06-09"

ingest_one() {
  local tenant="$1" path="$2" doc_class="$3" far_part="${4:-}"
  local name; name="$(basename "${path}")"
  local meta="{\"source_doc_name\":\"${name}\",\"snapshot_date\":\"${SNAPSHOT_DATE}\",\"doc_class\":\"${doc_class}\""
  [ -n "${far_part}" ] && meta="${meta},\"far_part\":\"${far_part}\""
  meta="${meta}}"

  local status body
  body="$(mktemp)"
  status="$(curl -sS -o "${body}" -w '%{http_code}' \
    -X POST "${BASE_URL}/ingest/document" \
    -H "X-Tenant-ID: ${tenant}" \
    -H "Authorization: admin" \
    -F "file=@${path}" \
    -F "metadata=${meta}" \
    -F "format=md")"
  case "${status}" in
    200) echo "  [${tenant}] ${name}: $(jq -r '.chunks_inserted' "${body}") chunks";;
    409) echo "  [${tenant}] ${name}: duplicate - skipped";;
    *)   echo "  [${tenant}] ${name}: FAIL ${status}"; cat "${body}"; rm -f "${body}"; return 1;;
  esac
  rm -f "${body}"
}

for tenant in "${TENANTS[@]}"; do
  echo "== tenant ${tenant}"
  ingest_one "${tenant}" "${ROOT}/docs/reference/far/far-part-15.md" far_reference 15
  ingest_one "${tenant}" "${ROOT}/docs/reference/far/far-part-52.md" far_reference 52
  for f in "${ROOT}"/docs/reference/synthetic-solicitations/*/SOL-*.md; do
    ingest_one "${tenant}" "${f}" synthetic_solicitation
  done
done
echo "== SEED DONE"
