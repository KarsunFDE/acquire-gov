.PHONY: help verify-debt-locks verify-debt-lockfile-schema run-locked-tests check-lint-disabled check-dockerfile-latest

help:
	@echo "Targets:"
	@echo "  verify-debt-locks               Run all debt-enforcement checks (same as CI)"
	@echo "  verify-debt-lockfile-schema     Schema-validate docs/debt-lockfile.yml"
	@echo "  run-locked-tests                Run all locked-failing tests; assert still failing"
	@echo "  check-lint-disabled             Item-12 locked-failing check (shell)"
	@echo "  check-dockerfile-latest         Item-11 locked-failing check (shell)"

verify-debt-locks: verify-debt-lockfile-schema run-locked-tests
	@echo "OK: debt-preservation invariant intact"

verify-debt-lockfile-schema:
	python3 .github/scripts/verify-debt-lockfile.py docs/debt-lockfile.yml

run-locked-tests:
	bash .github/scripts/run-locked-tests.sh docs/debt-lockfile.yml

check-lint-disabled:
	@bash .github/scripts/check-lint-disabled.sh; \
	if [ $$? -eq 1 ]; then echo "(expected — debt 12 still locked)"; fi

check-dockerfile-latest:
	@bash .github/scripts/check-dockerfile-latest.sh; \
	if [ $$? -eq 1 ]; then echo "(expected — debt 11 still locked)"; fi
