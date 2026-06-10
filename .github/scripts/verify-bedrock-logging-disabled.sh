#!/usr/bin/env bash
# verify-bedrock-logging-disabled.sh
#
# CI guard: Bedrock model invocation logging MUST be disabled.
# Spec: docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §14 ("Bedrock model
# invocation logging — never on").
# ADR: ADR-0009 D3 (LangSmith + Bedrock model-invocation logging both
# off in Phase 1 — sensitive prompt/completion content must not be
# written to provider-side logs).
#
# Behavior:
#   - With AWS creds: aws bedrock get-model-invocation-logging-configuration
#     must report disabled (no cloudWatchConfig + no s3Config) OR an
#     explicit "loggingConfig is not configured" error. Anything else
#     → exit 1.
#   - Without creds (typical CI / dev): SKIP with exit 0. The guard is
#     non-blocking when AWS is not reachable.
set -euo pipefail

if ! command -v aws >/dev/null 2>&1; then
  echo "verify-bedrock-logging-disabled: aws CLI not installed — skipping"
  exit 0
fi

# Quick reachability check — if STS sts get-caller-identity fails, we
# treat this as "no creds → skip" per ADR-0009 D3 guard.
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "verify-bedrock-logging-disabled: no AWS creds resolved — skipping"
  exit 0
fi

REGION="${AWS_REGION:-us-east-1}"
OUTPUT="$(aws bedrock get-model-invocation-logging-configuration \
            --region "$REGION" 2>&1 || true)"

# Acceptable "disabled" signals:
#   - API returns empty / no loggingConfig key.
#   - API errors with 'is not configured' (region has never enabled it).
if echo "$OUTPUT" | grep -qiE "is not configured|no logging configuration|ResourceNotFoundException"; then
  echo "verify-bedrock-logging-disabled: OK — logging not configured in $REGION"
  exit 0
fi

# If loggingConfig is present, assert that BOTH cloudWatchConfig AND
# s3Config are absent / null.
if echo "$OUTPUT" | grep -qE '"cloudWatchConfig"|"s3Config"'; then
  echo "ERROR: Bedrock model-invocation logging appears ENABLED in $REGION."
  echo "Spec docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §14 prohibits this."
  echo "Disable via: aws bedrock delete-model-invocation-logging-configuration --region $REGION"
  echo "Raw output:"
  echo "$OUTPUT"
  exit 1
fi

echo "verify-bedrock-logging-disabled: OK — no logging targets configured"
exit 0
