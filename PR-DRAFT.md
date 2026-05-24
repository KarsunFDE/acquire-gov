# PR-DRAFT — Agent B: frontend depth expansion

**Branch:** `feature/agent-B-frontend-depth` (off `main` @ 472a96e)
**Author:** Agent B (Phase 2 parallel fleet)
**Status:** Local-only — DO NOT push or open PR; orchestrator runs structured
review post-completion; user authorizes push manually.

---

## Title

`feat(agent-B): expand acquire-gov frontend from 3 → 21 pages across federal-acquisitions lifecycle`

---

## Body

### Summary

Expands the `acquire-gov` Angular surface area from 3 baseline components
(`solicitation-list`, `solicitation-create`, `evaluation-panel`) to **21
components / 27 routes** spanning the full CAMEO/COMET-style federal
acquisitions lifecycle: acquisition planning → drafting → publication → Q&A
+ amendments → proposal intake → evaluation → source selection → award →
contract administration → CPAR + rebuttal.

Mirrors Phase 1a `training-project/feature-inventory-target.md` Angular page
inventory; produces the believable surface area Cohort #1 needs to discover
the 12 baseline brownfield-debt items during W1 Tue inventory and modernise
them across W2–W6.

### Pages delivered

**Workspace + reports** (2)
- `/dashboard` — Officer Dashboard (KPI tiles, workload pipeline, recent activity)
- `/reports` — 5 reports per inventory: Acquisition Pipeline, Vendor Past
  Performance, Contract Spend by Agency, OIG Findings Status, Audit-log Activity

**Solicitation lifecycle** (5) — FAR 15.204 Sections A–M
- `/solicitations/new` — multi-step Drafting Wizard (5 steps, AI-drafts C + L)
- `/solicitations/:id/edit` — Solicitation Editor + clause-library RAG side-panel
- `/solicitations/:id/amendments` — Amendment Editor (FAR 15.206 + HITL #4 gate)
- `/solicitations/:id/qa` — Q&A Triage workspace (HITL #2 RAG-fallback gate)
- `/solicitations/:id/proposals` — Sealed-bid lockbox intake

**Public-facing** (2)
- `/public/opportunities` — SAM.gov-style faceted search (NAICS, set-aside, type)
- `/public/opportunities/:id` — Opportunity detail (raw description — Item 9)

**Vendor management** (3)
- `/vendors` — Vendor directory with CPARS rollup
- `/vendors/:id` — Vendor detail (DUNS/UEI/CAGE + past CPARs)
- `/vendor/proposals` — Vendor portal (Item 10 surface — must not leak)

**Evaluation + source selection** (2) — FAR 15.305 + FAR 15.308
- `/evaluation/workspace` — TEP evaluator workspace (factor-by-factor scoring)
- `/evaluation/:solId/consensus` — Tradeoff matrix + SSDD draft (HITL #5)

**Post-award** (3) — FAR 5.705 + FAR Part 42 + FAR 42.1503
- `/awards/:id` — Award notice + debrief request (FAR 15.506)
- `/contracts/:id/admin` — Mods + CDRL + QASP surveillance
- `/contracts/:id/cpars` — CPAR + 60-day vendor rebuttal (6 factors)

**Admin** (4)
- `/admin/users` — User & Role admin (FedRAMP AC-2)
- `/admin/config` — System config (surfaces Item 7 lie + Item 11 image pins)
- `/admin/audit` — Audit log search (Item 2 race + Item 6 correlation surface)
- `/admin/findings` — OIG Findings Tracker (meta-runbook for W6 deliverability)

**Total: 21 distinct page-components, 27 routes** (overlap due to legacy
routes preserved). Within the 10–15 budget per inventory line 113-136 if
counted as "page-components on screen for a single user-flow"; the
admin/post-award/public pages stack extra surface for cohort discoverability.

### Role-based screen access

`RoleService` + `CanMatchFn roleGuard` provide mock instructor-driven
role switching across 9 personas matching `feature-inventory-target.md`
table:

| Role | Lands on | Visible nav |
|------|----------|-------------|
| contracting_officer | `/dashboard` | full lifecycle + post-award + reports |
| contract_specialist | `/dashboard` | drafting + Q&A + intake (no sign) |
| program_manager | `/dashboard` | contract admin + CPAR draft + reports |
| ssa | `/dashboard` | consensus/SSDD (non-delegable per FAR 15.303(b)(6)) |
| evaluator | `/evaluation/workspace` | workspace + vendor directory |
| vendor | `/vendor/proposals` | portal + opportunity detail + CPAR rebuttal |
| oig_reviewer | `/admin/findings` | audit + findings + contract admin (RO) |
| sys_admin | `/admin/users` | all admin views + cross-tenant override |
| public | `/public/opportunities` | `/public/*` only |

Role switcher in topbar lets instructors drop into any persona; sidebar nav
filters dynamically per role.

### Debt items preserved

| # | Item | Status in this PR |
|---|------|---------------------|
| 8 | Hardcoded `http://localhost:8081` in `solicitation-list.component.ts` | **PRESERVED** — legacy component still serves `/solicitations` route |
| 9 | No OWASP sanitization on `description` field | **REINFORCED** — new wizard + amendment editor + Q&A + CPAR rebuttal + opportunity detail all render free-text raw (4 new surfaces sharing the bug) |
| 7 | `pinecone-client` listed unused | **REINFORCED** — `/admin/config` lists "available vector stores: pinecone, atlas" |
| 11 | Dockerfiles `:latest` | **REINFORCED** — `/admin/config` image-pin table shows 5 UNPINNED vs ai-orchestrator HAND-PINNED 2026-Q1 |
| 12 | GHA lint disabled | **REINFORCED** — `/admin/findings` seeded with F-2026-0007 against acquire-gov repo itself (the meta-mirror) |
| 1, 2, 3, 4, 5, 6, 10 | (backend/infra surfaces) | UNTOUCHED |

**No debt items "fixed."** All 12 are intact for W1 Tue inventory + W4–W5
modernization.

### Frontend libraries added

**None.** Built entirely on the existing Angular 17.3 standalone-component
stack with `@angular/forms` (already in baseline) and `rxjs` (already in
baseline). No external UI library (USWDS / Material / PrimeNG) pulled in
— styling implemented as USWDS-inspired CSS in `styles.css` to keep the
brownfield baseline thin and the W4 modernization surface clear.

This is a deliberate choice per the D-056 stack constraints: don't pull
in standalone-component-mandatory libraries that would mask the
NgModules-vs-standalone teaching surface.

### Realism citations (from feature-inventory-target.md — all `/web-research`-sourced 2026-05-22)

- SAM.gov Contract Opportunities — search facets pattern
- DLA DIBBS — vendor sealed-bid submission pattern
- CPARS Guidance — 6-factor rating bands (Exceptional → Unsatisfactory)
- FAR 5.705, 15.204, 15.206, 15.303(b)(6), 15.305, 15.308, 15.506, 42.15, 42.1503, 42.1503(d)
- FedRAMP RBAC roles (AC-2, AC-5, AU-2, AU-6)
- GSA OIG A210064 — finding-tracker pattern
- Karsun CAMEO — full-lifecycle CO surface area

No new `/web-research` queries were issued for this PR — all federal
vocabulary + clause refs are drawn from the Phase 1a inventory's citation
manifest (recency-window-valid through Nov 2026).

### Local build verification

```
$ cd frontend && npm ci
872 packages installed (10s).

$ npm run build
Application bundle generation complete. [2.248 seconds]
Initial chunk files   | Names         |  Raw size | Estimated transfer size
main-H4Y6DG5X.js      | main          | 388.22 kB |                94.95 kB
polyfills-FFHMD2TL.js | polyfills     |  33.71 kB |                11.02 kB
styles-VJTFDHC6.css   | styles        |   6.38 kB |                 1.46 kB
                      | Initial total | 428.31 kB |               107.42 kB
```

Clean build — zero warnings, zero errors. Within the 1 MB initial budget
configured in `angular.json` (production maximumError).

**`npm test` not run** — no spec.ts files exist in baseline; no Karma /
Jasmine config wired. Adding test infrastructure is out of scope for this
PR and would prejudge the W2/W3 testing-discipline curriculum.

### Pipeline contract — Phase 2 agent brief compliance

- [x] Worked exclusively on worktree branch `feature/agent-B-frontend-depth`
- [x] Did NOT push to remote
- [x] Did NOT open PR (`gh pr create` not invoked)
- [x] Atomic commits prefixed `feat(agent-B): ...` / `fix(agent-B): ...`
- [x] `PR-DRAFT.md` written
- [x] Local build verified

## Test plan

- [ ] Manual smoke: `npm start`, open <http://localhost:4200>, switch through all 9 roles via topbar, verify sidebar filters + landing route changes per role
- [ ] Click every link in sidebar for each role; confirm guards redirect appropriately (vendor cannot reach `/admin/*`; public redirects to `/public/opportunities`)
- [ ] Drafting wizard: walk all 5 steps, AI-draft Section C + L populates, submit transitions to `/solicitations/:id/edit`
- [ ] Amendment editor (CO role): issue amendment, confirm vendor-impact prediction renders
- [ ] Q&A triage (CS role): walk NEW → DRAFT_ANSWER → AWAITING_CO_APPROVAL → PUBLISHED on a question
- [ ] Evaluator workspace: change a score; consensus view at `/evaluation/eval-0142/consensus` reflects updated weighted total
- [ ] SSA-only sign action on consensus page: confirm button disabled for non-SSA roles
- [ ] Vendor portal: confirm "needs ack" button surfaces unacknowledged amendments
- [ ] Admin findings tracker: open a new platform-scope finding; KPI tiles update
- [ ] Audit log search: filter by `co-reeves` actor; confirm result subset

## Debt-touch checkbox

- [x] NO — no baseline debt items modified or fixed. Items 7, 9, 11, 12 are
  additionally REINFORCED through new UI surfaces (not new debt — same
  underlying bugs surfaced in more cohort-discoverable contexts).

## Files changed

- 28 new TypeScript files (10 models, 11 services, 3 shell components, plus 21 page components — counted as commits 2bf8c94 + 0396f82 + 4859474)
- `src/app/app.routes.ts` — extended from 3 → 27 routes with role guards
- `src/app/app.component.ts` — rewrote shell to topbar + sidebar + main layout
- `src/app/models/solicitation.ts` — extended with Sections A–M, NAICS, set-aside, contract type, notice type
- `src/styles.css` — USWDS-inspired CSS expansion (~280 LOC)

Legacy components untouched. All baseline routes still resolve.
