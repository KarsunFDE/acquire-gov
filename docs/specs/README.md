# `docs/specs/` — feature specs index

One folder per feature / milestone. Each folder owns its own design reference, implementation tracker (if active), per-phase specs, and supporting docs.

| Folder | Status | Entry point |
|---|---|---|
| [`m1-agentic-drafting/`](./m1-agentic-drafting/) | **active** — Phase 0 not yet started; ADRs 0012-0015 + design reference + 6 phase specs ready | [`m1-agentic-drafting/tracker.md`](./m1-agentic-drafting/tracker.md) |
| [`m2-grounded-retrieval/`](./m2-grounded-retrieval/) | **shipped** 2026-06-10 (commit `c61a2e3` integration) — 21 PRs merged | [`m2-grounded-retrieval/handoff.md`](./m2-grounded-retrieval/handoff.md) |

## Conventions

- **Per-feature folder.** Each milestone or feature gets its own folder. File names inside the folder drop redundant milestone prefixes (`m1-tracker.md` → `tracker.md`).
- **Tracker is the entry point** for any active feature. It tracks phase status, owns the crash-recovery checklist, and links to per-phase specs.
- **Design reference vs. implementation tracker.** The design-reference doc captures endpoint contracts + schemas + tool internals (the *what*). The tracker + per-phase specs own implementation order (the *when* + *how*).
- **Phases live under `phases/`** subdirectory inside the feature folder. Numbered `0-foundation.md`, `1-vertical-slice.md`, etc. Vertical slices (UI + API end-to-end) are explicit in each phase's title.
- **HTML visualizations** sit alongside their design reference (e.g., `topology.html`). No build step — open in a browser.

## When starting a new feature

Create `docs/specs/{milestone}-{feature-slug}/` with:

1. `README.md` — one-paragraph orientation + links to ADRs that govern this feature
2. `design-reference.md` — endpoint contracts, schemas, tool internals; the *what*
3. `tracker.md` — phase status table + active-phase block + crash-recovery checklist; the *when*
4. `phases/{N}-{slug}.md` — per-phase implementation specs
5. Optional: `topology.html`, `handoff.md`, supporting reference docs

## When closing out a feature

After all phases land:

1. Tracker §1 shows every phase `completed`.
2. Add a `handoff.md` to the folder summarizing shipped state, deferred items, and verification one-liners.
3. Update the top-level `Status` column in this file from `active` to `shipped` with the date and integration commit SHA.
4. Leave the design reference + phase specs in place — they remain the documented contract.
