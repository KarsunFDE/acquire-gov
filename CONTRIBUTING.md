# Contributing to acquire-gov

`acquire-gov` is the **trainer brownfield** for the Karsun-FDE 6-week
intensive. It ships with 12 deliberately preserved brownfield-debt items
that the cohort discovers, lives with, and modernizes on schedule.

## Brownfield debt — the 12 items

If you find code that "looks broken" — verify against
[`docs/brownfield-debt.md`](docs/brownfield-debt.md) **before fixing it**.
The 12 items are curriculum lifeblood; modernizing them outside their
scheduled week breaks the teaching arc for the entire cohort.

Mechanical enforcement lives in
[`docs/debt-lockfile.yml`](docs/debt-lockfile.yml) +
[`.github/workflows/debt-enforcement.yml`](.github/workflows/debt-enforcement.yml).

### Scheduled modernization weeks

| Item | Subject | Scheduled week |
|------|---------|----------------|
| 1    | JWT signature-skip on `/api/public/*`        | **W4-Wed** (AI Security Day) |
| 2    | Audit-log race in solicitation-service       | **W3 multi-agent** or **W5-Wed** (AIOps gov) |
| 3    | Missing circuit breaker (eval → solicitation)| **W4-Thu** (reliability) |
| 4    | No structured-output validation              | **W1-Fri** (LLM Essentials Day 2) |
| 5    | Pre-v1.0 LangChain patterns (`chain.run()`)  | **W2-Mon** (RAG anchor) |
| 6    | Inconsistent correlation-IDs                 | **W1-Tue** structured-logging + **W5-Tue** OTel |
| 7    | Unused `pinecone-client` dependency          | **W2-Mon** (Atlas Vector Search) |
| 8    | Frontend hardcodes service URL               | **W4-Tue** (API modernization) |
| 9    | No OWASP input sanitization                  | **W4-Wed** (AI Security Day) |
| 10   | No multi-tenant boundary                     | **W2-Wed** (multi-tenant RAG) |
| 11   | Dockerfile `:latest` tags                    | **W4-Wed** (OWASP LLM03 supply chain) |
| 12   | GHA workflow disables linting                | **W4-Tue** (spec-driven dev) |

(Cross-reference [`docs/brownfield-debt.md`](docs/brownfield-debt.md) for
the *fixed-looks-like* description per item.)

## CI catches accidental fixes

If you submit a PR that accidentally modernizes a still-locked item, the
`debt-enforcement` job will block your PR with a message like:

> ❌ Debt item 4 (no-structured-output-validation) appears modernized, but
> lockfile says locked. Update `docs/debt-lockfile.yml` (flip `locked: true`
> → `false`) and apply the `debt-touch-approved` label.

Two things you should do when you see that:

1. **Verify with your instructor** that this item is actually scheduled
   for this week. If not, revert your change.
2. **If it IS scheduled**: follow the modernization flow below.

## How to legitimately modernize a debt item

1. **Plan Day authorization.** Your week's Plan Day Mon-morning agenda
   confirms which items are scheduled this week. Don't touch items out of
   schedule.
2. **Branch from `main`.** Keep PR scope narrow — one item per PR where
   possible.
3. **Update the lockfile.** Edit `docs/debt-lockfile.yml` — flip
   `locked: true` → `locked: false` for items you're modernizing.
4. **Fill the PR template.** Tick the **YES** branch, list the item IDs,
   complete the modernization-week alignment table.
5. **Request the label.** Ask your instructor to apply
   `debt-touch-approved` to the PR.
6. **CI passes, merge.** Once the label is on and CI is green, the PR is
   mergeable.

## How to NOT accidentally modernize

- **Keep PR scope narrow.** If your PR touches `services/api-gateway/`,
  re-read items 1, 6, and 11 of the debt doc before pushing.
- **Run `make verify-debt-locks` locally.** Same check CI runs. If it
  passes locally, it'll pass in CI.
- **Read the file headers.** Several files have
  `// ⚠ DELIBERATE — Item N` banners — leave them alone unless modernizing
  on schedule.

## Other contribution guidance

### Branch naming

`<initials>/<short-description>` — e.g., `jc/item-4-pydantic-validation`.

### Commit format

Conventional commits. Type prefixes:
- `feat`: new capability (not a debt fix)
- `fix`: bug fix (a *real* bug, not a debt item)
- `debt`: modernization of a scheduled debt item (e.g., `debt(item-4): ...`)
- `docs`, `chore`, `test`, `refactor`, `perf`: as usual

Modernization commits MUST use the `debt(item-N): ...` prefix.

### Local development

```bash
docker-compose up        # all 5 services
make verify-debt-locks   # mechanical debt enforcement (same as CI)
```

Per-service:
```bash
# Java services:
cd services/api-gateway && mvn -B test
# Python:
cd services/ai-orchestrator && pytest tests/
# Angular:
cd frontend && npm test
```

### ADRs

Per-pair modernization decisions land under `docs/adrs/`. ADR-0001 is the
pair's aspect commitment. ADR-0002+ are modernization choices (one per
significant debt fix or architectural decision).

## Questions?

If you find debt-like code that *isn't* in the 12-item inventory: open an
issue with the `instructor-review` label. There are intentional
reinforcement gaps (no healthchecks in docker-compose, postgres volume not
persisted, deploy.yml is a stub) — see the *Reinforcement gaps* section of
`docs/brownfield-debt.md`. Those reinforce the 12 items rather than being
12+N.
