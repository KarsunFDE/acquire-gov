# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`acquire-gov` is the **trainer brownfield** for the Karsun-FDE 6-week intensive (federal-acquisitions domain). It is **deliberately imperfect** — it ships with **12 preserved brownfield-debt items** that the cohort discovers in W1 Tue and modernizes on a fixed schedule across W2–W5. It is also the **template** from which 3 pair-projects (`grants-portal-modern`, `contract-payment-flow`, `foia-response-pipeline`) are generated.

**Read `docs/brownfield-debt.md` before "fixing" anything that looks broken.** The 12 items are curriculum lifeblood; modernizing them outside their scheduled week breaks the teaching arc for the whole cohort and is blocked by CI.

## Phase 1 — AI Adoption (current phase)

Full PRD: [`docs/prd/phase-1-ai-adoption.md`](docs/prd/phase-1-ai-adoption.md). The mental model future Claude instances need:

- **Phase 1 = adoption, not modernization.** AI is layered on top of the stack as it stands. Don't pre-fix inherited debt that Phase 2 owns; surface it, note the blast radius, defer it. Framework/runtime/SDK hops, AI-security hardening of legacy debt, AIOps/OTel, circuit breakers, multi-tenant rollout beyond the retrieval boundary are all **out of scope** in Phase 1.
- **The PRD is *what + why*, not *how*.** Endpoint shapes, retrieval approach, gate primitives, confidence thresholds, graph-vs-relational, streaming UX are deliberately deferred to planning sessions and captured as ADRs under `docs/adrs/`. If asked to make one of those choices, point at the PRD's Open Questions (§11) rather than hard-coding.
- **Three capabilities, delivered in sequence:**
  - **M1 — LLM-assisted solicitation drafting** (REQ-AID-1..4): structured drafts, no malformed/ungrounded output reaches downstream, cost attributable per tenant/feature, no issuance without recorded CO approval.
  - **M2 — Grounded retrieval** (REQ-RAG-1..4): FAR/DFARS-cited answers, withhold-and-escalate on low confidence, cross-tenant retrieval impossible (proven by test), eval gate blocks grounding regressions.
  - **M3 — Agentic source-selection workflow** (REQ-AGT-1..5): evaluation → consensus → SSA → award on synthetic data; hard gates on every statutorily-reserved or irreversible step (FAR 15.308 SSA, 5.705 award, 15.206 amendment); paused runs survive multi-day human delays; relational CO traversal questions answerable at interactive speed.
- **Cross-cutting principles (non-negotiable):**
  - **Authority over accuracy** — gates exist for accountability, not model quality. Model confidence never downgrades a hard gate.
  - **Grounded or withheld** — no authoritative answer ships without a real citation; weak grounding escalates, never guesses.
  - **Eval as the gate** — quality is proven by automated evaluation in CI, not manual inspection.
  - **Synthetic + FedRAMP-safe** — synthetic data only; **AWS Bedrock is the sole LLM path** (no direct third-party model APIs); managed Bedrock products (Knowledge Bases, Agents, Guardrails) are hand-built in Phase 1.
  - **Auditable by default** — sensitive/AI-assisted decisions write an append-only, OIG-replayable record.
- **Domain model:** ~17-entity graph; spine is `Vendor ↔ Proposal ↔ Evaluation ↔ Award ↔ ContractModification ↔ Cpar`. Canonical enumeration lives in external `fde-10-week/training-project/feature-inventory-target.md`. Volumes are modest (~100 vendors / ~500 proposals / ~80 active contracts per agency); graph-store vs. relational-traversal is an open planning question.

## Architecture (5 services)

Angular SPA → Spring Cloud Gateway → 2 Spring Boot microservices + Python/FastAPI AI orchestrator → Postgres + MongoDB + AWS Bedrock.

| Path | Stack | Port |
|------|-------|------|
| `frontend/` | Angular 17 | 4200 |
| `services/api-gateway/` | Spring Boot 2.7.18 + Spring Cloud Gateway + OAuth2 RS, Java 11 | 8080 |
| `services/solicitation-service/` | Spring Boot 2.7.18 + JPA(Postgres) + MongoDB, Java 11 | 8081 |
| `services/evaluation-service/` | Spring Boot 2.7.18, Java 11 | 8082 |
| `services/ai-orchestrator/` | Python 3.11 + FastAPI + LangChain v1.0 + Pydantic v2 + boto3 1.39.11 | 8000 |

All three Spring services run **SB 2.7.18 / Java 11** — that's the brownfield baseline, not a mistake to normalize. The W4 modernization target is **SB 4.0.x + Java 21** (Phase 2 territory; do not pre-do it).

`evaluation-service` calls `solicitation-service` directly (not through the gateway) — this coupling is deliberate and is what surfaces Item 3 (missing circuit breaker).

The ai-orchestrator's Bedrock call is a **stub** returning mock JSON; W1 Thu cohort work wires up real Bedrock.

## Common commands

```bash
# Full stack
docker-compose -f infra/docker/docker-compose.yml up --build

# Debt enforcement (same checks as CI)
make verify-debt-locks            # all checks
make verify-debt-lockfile-schema  # schema-validate docs/debt-lockfile.yml
make run-locked-tests             # assert every locked item's test still fails

# Per-service
cd services/api-gateway && mvn -B test           # also: solicitation-service, evaluation-service
cd services/ai-orchestrator && pytest tests/
cd frontend && npm test                          # ng test under the hood
cd frontend && npm run build                     # ng build
```

Run a single test:
- Java: `mvn -B test -Dtest=ClassName` (in the service dir)
- Python: `pytest tests/test_file.py::test_name` (in `services/ai-orchestrator`)
- Pytest debt markers: `pytest -m brownfield_debt_4` (markers defined in `services/ai-orchestrator/pytest.ini`)

## The brownfield-debt invariant (the most important thing in this repo)

Twelve items in `docs/brownfield-debt.md` are mechanically locked via `docs/debt-lockfile.yml`. For every locked item there is a **locked-failing test** that MUST keep failing. `.github/workflows/debt-enforcement.yml` runs `.github/scripts/run-locked-tests.sh` on every PR; if a locked test starts passing without the lockfile being updated, the PR is blocked.

**Before touching a file:**
- Check `docs/brownfield-debt.md` to see if it's named in any item's "Where" section.
- Look for `⚠ DELIBERATE — Item N` header banners — leave them alone unless modernizing on schedule.
- Several reinforcement gaps (no postgres volume mount, no docker healthchecks, deploy.yml is a stub) are also deliberate.

**Legitimate modernization flow:** flip `locked: true` → `false` in `docs/debt-lockfile.yml` for the item being fixed, fill in the PR template's YES branch, and request the `debt-touch-approved` label. CI checks the PR-template checkbox state against the lockfile diff via `.github/scripts/verify-pr-debt-checkbox.py`.

`run-locked-tests.sh` knows to clear the pom-level `excludedGroups` (which keeps the `brownfield_debt` umbrella out of default `mvn test`) when running locked tests in isolation — don't change that without re-reading the script's comments.

## Commit / branch conventions

- Branch: `<initials>/<short-description>` (e.g., `jc/item-4-pydantic-validation`).
- Conventional commits. `debt(item-N): ...` is required for modernization commits (separate from `fix:` for real bugs).
- Per-pair modernization decisions land as ADRs in `docs/adrs/`.

## Planning + ADR workflow

- **Multi-ADR planning sessions require a fresh critic pass against PRD scope-out before declaring done.** If a single session produces 3+ ADRs, spawn a fresh agent (one that has not seen the planning conversation) with the PRD + the produced ADRs + this file. Prompt it to be ruthless against PRD §4 (out of scope) and §11 (open questions deferred to planning). Author bias is the failure mode you're correcting for — the 2026-06-01 M2 planning session smuggled in three scope violations (full app-side OTel rollout, host-disk-encryption cohort prereq, scheduled human-review time budget) that the author did not catch during writing.
- Watchwords that should trigger immediate scope-out re-check: OTel / OpenTelemetry / AIOps / circuit breaker / resilience engineering / observability tooling / dashboard JSON / encryption prereqs / multi-tenant rollout beyond retrieval boundary / AI-security hardening of legacy debt / scheduled human-review time.
- If an ADR closes one of PRD §11's open questions, that's pre-empting planning authority unless the user explicitly authorized it — re-verify before merge.
- Tradeoff: small token cost on every multi-ADR session for big scope-discipline value. Run the critic pass.

## Pair-project portability

Daily tasks given against `acquire-gov` apply to all 3 pair-projects because the 12 baseline items + architecture + file-pattern shape are constant. The `pair-brownfield-generator` skill (run W1 Wed PM) renames services per pair's domain (solicitation → grant/contract/foia) and adds 4–6 pair-unique debt items; baseline parity across pairs is assessment-critical, so do not "tidy" baseline items during reshape.

## Things to know before suggesting fixes

- All three Spring services are on **SB 2.7.18 / Java 11**. W4 modernizes the whole tier to SB 4.0.x + Java 21 — don't pre-do it.
- **Bedrock auth (D-060):** `infra/docker/docker-compose.yml` reads the repo-root `.env` (`required: false`) so the stack still runs without creds. Preferred path is `AWS_BEARER_TOKEN_BEDROCK` (needs `boto3 >= 1.39.11`; auto-used by `boto3.client("bedrock-runtime")` with no code change). IAM access-key/secret still works. Stub fallback kicks in when no creds are present — first-day learners rely on this.
- `BEDROCK_MODEL_ID` is set in **three places** (`.env.example`, `docker-compose.yml` `environment:`, `bedrock_client.py`) with no single source of truth — deliberate drift the cohort consolidates. Compose's `environment:` wins over `env_file:`, so editing `.env` alone won't change the model in the container; remove the line from compose to let `.env` drive it. The pinned ID is intentionally a generation behind current GA.
- `services/ai-orchestrator/Dockerfile` is pinned to `python:3.11-slim` — that pin is itself a teaching artifact (numpy/pydantic-core wheels broke on Python 3.14 in 2026-Q1). The other 4 Dockerfiles still use `:latest` (Item 11) — don't pin them.
- `services/ai-orchestrator/app/legacy_chain.py` (pre-v1.0 `LLMChain.run()`) coexists with v1.0 patterns in `app/main.py`. Both styles are expected to be present until W2 Mon.
- CI lint step is commented out (Item 12). Don't uncomment it.
- The current AI path returns raw, ungrounded model output with no validation — that's the OIG-defensibility problem Phase 1 is solving (PRD §2). Output validation, citations, and HITL gates are work to *do*, not assumed-present infrastructure.
