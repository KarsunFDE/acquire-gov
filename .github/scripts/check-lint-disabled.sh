#!/usr/bin/env bash
# brownfield_debt_12 locked-failing check.
#
# While debt 12 is locked: lint steps in .github/workflows/ci.yml are
# commented out. This script greps for commented `name: Lint` lines and
# EXITS 1 (debt present, locked invariant holds).
#
# When debt 12 is modernized (W4-Tue): lint steps are uncommented and
# this script EXITS 0. CI's run-locked-tests.sh then catches that the
# locked-failing test started passing -> lockfile must be updated +
# debt-touch-approved label applied.
#
# Spec: fde-10-week/pipeline/T27-debt-enforcement-spec.md

set -u

CI_YAML="${CI_YAML:-.github/workflows/ci.yml}"

if [ ! -f "$CI_YAML" ]; then
    echo "::error::CI workflow not found: $CI_YAML" >&2
    exit 2
fi

# Look for any line of the shape `#   - name: Lint ...` indicating disabled lint.
if grep -qE '^\s*#\s*-\s*name:\s*Lint' "$CI_YAML"; then
    echo "LOCKED: lint steps in $CI_YAML are commented (debt 12 still present)"
    exit 1
fi

echo "MODERNIZED: lint steps in $CI_YAML are active (debt 12 unlocked)"
exit 0
