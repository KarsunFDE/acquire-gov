#!/usr/bin/env bash
# Run each locked debt-item's locked-failing test. Assert it FAILS.
# If a locked test passes, debt was modernized without lockfile update -> CI fails.
#
# Spec: fde-10-week/pipeline/T27-debt-enforcement-spec.md
# Usage: run-locked-tests.sh docs/debt-lockfile.yml

set -u

LOCKFILE="${1:-docs/debt-lockfile.yml}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if [ ! -f "$LOCKFILE" ]; then
    echo "::error::Lockfile not found: $LOCKFILE" >&2
    exit 1
fi

# Parse lockfile via python (yaml already required by sibling script).
python3 - <<'PY' "$LOCKFILE"
import sys
import yaml
with open(sys.argv[1]) as fh:
    data = yaml.safe_load(fh)
for item in data["items"]:
    print(f"{item['id']}\t{item['locked']}\t{item['test_marker']}\t{item['test_path']}\t{item['name']}")
PY

if [ $? -ne 0 ]; then
    echo "::error::Failed to parse $LOCKFILE" >&2
    exit 1
fi

FAILED_LOCKED_CHECKS=()
PASSED_LOCKED_CHECKS=()
PENDING_TEST_AUTHOR=()

while IFS=$'\t' read -r ITEM_ID LOCKED MARKER TEST_PATH NAME; do
    [ -z "$ITEM_ID" ] && continue
    FULL_PATH="$REPO_ROOT/$TEST_PATH"

    if [ "$LOCKED" != "True" ] && [ "$LOCKED" != "true" ]; then
        echo "::notice::Item $ITEM_ID ($NAME) is UNLOCKED — skipping locked-test check"
        continue
    fi

    if [ ! -e "$FULL_PATH" ]; then
        echo "::warning::Item $ITEM_ID ($NAME) test not yet authored: $TEST_PATH (iter-12 owed)"
        PENDING_TEST_AUTHOR+=("$ITEM_ID:$NAME")
        continue
    fi

    case "$TEST_PATH" in
        *.java)
            SERVICE_DIR=$(echo "$TEST_PATH" | cut -d/ -f1-2)
            cd "$REPO_ROOT/$SERVICE_DIR" || exit 1
            CLASS_NAME=$(basename "$TEST_PATH" .java)
            # Clear the pom-level excludedGroups (@Tag "brownfield_debt" umbrella
            # exclusion that keeps debt tests OUT of default `mvn test`) so this
            # targeted run can actually exercise the locked-failing test.
            # Also force `failsafe.classes.includes` to match — `-Dtest=` selector
            # alone is overridden by `excludedGroups` otherwise (test skipped,
            # mvn exits 0, script falsely reports "now passing").
            if mvn -B -q test -Dtest="$CLASS_NAME" -DexcludedGroups= -DfailIfNoTests=true > /tmp/locked-test-$ITEM_ID.log 2>&1; then
                PASSED_LOCKED_CHECKS+=("$ITEM_ID:$NAME ($TEST_PATH)")
            else
                FAILED_LOCKED_CHECKS+=("$ITEM_ID:$NAME")
            fi
            cd "$REPO_ROOT" || exit 1
            ;;
        *.py)
            cd "$REPO_ROOT/services/ai-orchestrator" 2>/dev/null || cd "$REPO_ROOT"
            if python -m pytest -m "$MARKER" --no-header -q "$REPO_ROOT/$TEST_PATH" > /tmp/locked-test-$ITEM_ID.log 2>&1; then
                PASSED_LOCKED_CHECKS+=("$ITEM_ID:$NAME ($TEST_PATH)")
            else
                FAILED_LOCKED_CHECKS+=("$ITEM_ID:$NAME")
            fi
            cd "$REPO_ROOT" || exit 1
            ;;
        *.sh)
            if bash "$FULL_PATH" > /tmp/locked-test-$ITEM_ID.log 2>&1; then
                PASSED_LOCKED_CHECKS+=("$ITEM_ID:$NAME ($TEST_PATH)")
            else
                FAILED_LOCKED_CHECKS+=("$ITEM_ID:$NAME")
            fi
            ;;
        *.ts|*.spec.ts)
            cd "$REPO_ROOT/frontend" || exit 1
            if npx ng test --watch=false --include="$TEST_PATH" > /tmp/locked-test-$ITEM_ID.log 2>&1; then
                PASSED_LOCKED_CHECKS+=("$ITEM_ID:$NAME ($TEST_PATH)")
            else
                FAILED_LOCKED_CHECKS+=("$ITEM_ID:$NAME")
            fi
            cd "$REPO_ROOT" || exit 1
            ;;
        *)
            echo "::error::Item $ITEM_ID has unsupported test_path extension: $TEST_PATH"
            exit 1
            ;;
    esac
done < <(python3 - <<'PY' "$LOCKFILE"
import sys
import yaml
with open(sys.argv[1]) as fh:
    data = yaml.safe_load(fh)
for item in data["items"]:
    print(f"{item['id']}\t{item['locked']}\t{item['test_marker']}\t{item['test_path']}\t{item['name']}")
PY
)

echo ""
echo "============================================"
echo "Locked-test summary"
echo "============================================"
if [ ${#PENDING_TEST_AUTHOR[@]} -gt 0 ]; then
    echo "PENDING test author (iter-12 owed): ${#PENDING_TEST_AUTHOR[@]} items"
    for x in "${PENDING_TEST_AUTHOR[@]}"; do echo "  - $x"; done
fi
echo ""
echo "LOCKED + still failing (good): ${#FAILED_LOCKED_CHECKS[@]} items"
if [ ${#FAILED_LOCKED_CHECKS[@]} -gt 0 ]; then
    for x in "${FAILED_LOCKED_CHECKS[@]}"; do echo "  - $x"; done
fi
echo ""
echo "LOCKED but now PASSING (BAD): ${#PASSED_LOCKED_CHECKS[@]} items"
if [ ${#PASSED_LOCKED_CHECKS[@]} -gt 0 ]; then
    for x in "${PASSED_LOCKED_CHECKS[@]}"; do echo "  - $x"; done
fi

if [ ${#PASSED_LOCKED_CHECKS[@]} -gt 0 ]; then
    echo ""
    echo "::error::Debt items appear modernized but lockfile says locked."
    echo "::error::Update docs/debt-lockfile.yml (flip locked: true -> false)"
    echo "::error::and apply the debt-touch-approved label."
    exit 1
fi

echo ""
echo "OK: all locked items still locked. Debt-preservation invariant intact."
