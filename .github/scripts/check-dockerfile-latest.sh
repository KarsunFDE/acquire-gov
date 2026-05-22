#!/usr/bin/env bash
# brownfield_debt_11 locked-failing check.
#
# 4 Dockerfiles still pin to :latest tags:
#   services/api-gateway/Dockerfile
#   services/solicitation-service/Dockerfile
#   services/evaluation-service/Dockerfile
#   frontend/Dockerfile (uses :latest twice — node + nginx)
#
# Exception: services/ai-orchestrator/Dockerfile was hand-pinned to
# python:3.11-slim in 2026-Q1 — teaching artefact, not under lockfile guard.
#
# While debt 11 is locked: at least one of those 4 Dockerfiles still says
# :latest. Exit 1.
# When debt 11 is modernized (W4-Wed): all 4 pinned. Exit 0.
#
# Spec: fde-10-week/pipeline/T27-debt-enforcement-spec.md

set -u

GUARDED_DOCKERFILES=(
    services/api-gateway/Dockerfile
    services/solicitation-service/Dockerfile
    services/evaluation-service/Dockerfile
    frontend/Dockerfile
)

LATEST_FOUND=()
for f in "${GUARDED_DOCKERFILES[@]}"; do
    if [ ! -f "$f" ]; then
        echo "::error::Guarded Dockerfile missing: $f" >&2
        exit 2
    fi
    if grep -qE '^\s*FROM\s+[^:[:space:]]+:latest' "$f"; then
        LATEST_FOUND+=("$f")
    fi
done

if [ ${#LATEST_FOUND[@]} -gt 0 ]; then
    echo "LOCKED: ${#LATEST_FOUND[@]} Dockerfile(s) still use :latest (debt 11 still present):"
    for f in "${LATEST_FOUND[@]}"; do echo "  - $f"; done
    exit 1
fi

echo "MODERNIZED: all 4 guarded Dockerfiles are pinned (debt 11 unlocked)"
exit 0
