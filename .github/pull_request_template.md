## What changed

<!-- One-line summary. -->

## Touches named brownfield-debt items?

This codebase has **12 deliberately preserved brownfield-debt items**
(see [`docs/debt-lockfile.yml`](../docs/debt-lockfile.yml) +
[`docs/brownfield-debt.md`](../docs/brownfield-debt.md)). CI's
debt-enforcement job blocks this PR if it mutates a locked item without
the `debt-touch-approved` label.

Pick **one**:

- [ ] **NO** — this PR does not touch any debt item. (Default.)
- [ ] **YES** — this PR modernizes debt item(s): _______ (list IDs, comma-separated)
  - [ ] I have updated `docs/debt-lockfile.yml` to flip `locked: true` → `false` for the listed items.
  - [ ] I am requesting the `debt-touch-approved` label from the instructor.

## Modernization-week alignment (only fill if YES)

For each touched item, state the `scheduled_unlock_week` from the lockfile
vs. the actual week of this PR:

| Item # | `scheduled_unlock_week` | Actual week | Aligned? |
|--------|-------------------------|-------------|----------|
| ?      | ?                       | ?           | ?        |

## Why this PR is the right shape

<!-- One paragraph: what this PR does and why. For modernization PRs,
include the architectural decision driving the change (link ADR). -->

## Checklist

- [ ] Tests pass locally (`mvn test` / `pytest` / `npm test` as relevant)
- [ ] `make verify-debt-locks` passes locally (same as CI debt-enforcement)
- [ ] If touching debt: ADR added under `docs/adrs/` for the modernization decision
