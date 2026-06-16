<!--
  Describe the actual change FIRST — don't ship a blank body.
  Generate the Summary with Claude from your branch:

    git fetch origin
    claude -p "Summarize this branch's diff vs origin/main as a PR description.
               List the explicit changes (one bullet each), the files touched and
               why each changed, and any user-facing impact. Concise markdown."

  Paste the output below, then review it — you own what you submit.
-->

## Summary

<!-- Claude-drafted from your diff (prompt in the comment above), then trimmed by you. -->

**Changes — explicit, one bullet per discrete change:**
-

**Files touched:**

<!-- one bullet per file — format: `path/to/file` — why it changed -->
-

## Why this change

<!-- The problem it solves; link an ADR under docs/adrs/ or a ticket if any. -->

---

<!-- ───── Governance / brownfield-debt — keep at bottom, fill as we build the AI orchestrator ───── -->

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

## Checklist

- [ ] Summary lists the explicit changes AND the files touched (Claude-drafted + human-reviewed), not the empty template
- [ ] Tests pass locally (`mvn test` / `pytest` / `npm test` as relevant)
- [ ] `make verify-debt-locks` passes locally (same as CI debt-enforcement)
- [ ] If touching debt: ADR added under `docs/adrs/` for the modernization decision
