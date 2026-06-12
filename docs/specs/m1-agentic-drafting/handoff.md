# M1 close-out handoff (P5.4)

**Date:** 2026-06-11 (updated 2026-06-12) · **Branch:** `cj/m1-langchain-integration` · **Status:** all 6 phases completed (tracker §1).

Session pickup order: **§7 (next-session checklist)** → [`tracker.md`](./tracker.md) §1 → the relevant phase spec's "Handoff notes" §10.

---

## 1. Phase status snapshot

| Phase | Status | What shipped |
|---|---|---|
| 0 Foundation | completed | 35 Pydantic models (`app/agents/schemas.py`), M1 config knobs, MongoDBSaver singleton + thread_id helpers |
| 1 Single-section | completed | preflight gate, 6 tools, `build_section_drafter_agent`, `/section` rewrite, Step 1 reactive forms, section-card gating |
| 2 HITL | completed | live interrupt middleware, `/section/resume` + `/section/abandon`, orphan sweeper, Pending-CO-decision panel |
| 3 Batch coordinator | completed | per-AI-Part `Send` fan-out, Part II programmatic clauses, Part III passthrough, `/batch` + `/batch/resume`, multi-cost rate limit, Draft-AI-Parts button |
| 4 Critic | completed | 3 critic tools, critic agent, `/critic`, coordinator stub swap, Step 12 inline warnings |
| 5 Hardening | completed | 7 record-only eval metrics + CI summary emission, `req_aid_1` ×4, e2e smoke, trace reference, this doc |

## 2. Architecture summary

One FastAPI orchestrator hosts three LangChain v1.0 `create_agent` harnesses — SectionDrafter (FinalDraftSection), PartDrafter I/IV (PartDraftBundle), ConsistencyCritic (ConsistencyReport, no middleware/checkpointer) — plus a custom LangGraph `StateGraph` coordinator that fans out per-AI-FAR-Part via `Send`, resolves Part II clauses deterministically from a hash-pinned FAR matrix, and passes Part III through from the wizard. All drafter runs share one MongoDBSaver (TTL=None) so HITL interrupts survive multi-day pauses and process restarts; the HITL middleware interrupts on `compute_gate_decision` INPUT args (hitl band only), pre-Sonnet-spend. Preflight (ADR-0015) hard-rejects ungrounded requests before any agent spend; the warn-only critic is double-clamped (prompt + `clamp_phase1` boundary); every run writes an append-only audit row with a `tool_calls[]` sub-record.

## 3. Local dev notes (what live verification still needs)

- Backend suite: 440+ passing; the ONLY expected failures are the 3 locked-failing brownfield-debt tests (`test_structured_output_debt` ×2, `test_unused_deps_debt`). `pytest -m req_rag_3` = 14, `pytest -m req_aid_1` = 4.
- Mongo-dependent tests auto-skip without atlas-local (`test_checkpointer` integration, `test_pause_restart`). Run with the compose stack up before declaring the P2 exit gate fully verified.
- Real-Bedrock exit-gate items NOT yet executed this session: live `/section` draft against seeded corpus, LangSmith span-order checks, e2e smoke. Run order: `scripts/m1_p1_smoke.sh` → `m1_p3_smoke.sh` → `m1_p4_critic_smoke.sh` → `m1_e2e_smoke.sh`.
- Dev env: langchain 1.3.7 + langgraph-checkpoint-mongodb installed (was 0.3.7 — pre-v1). requirements.txt pins are authoritative.

## 4. Verification one-liners

```bash
# Backend
cd services/ai-orchestrator
python -m pytest tests/ -q                       # 3 expected debt failures only
python -m pytest -m req_rag_3 -q                 # 14 passed
python -m pytest -m req_aid_1 -q                 # 4 passed
python -m eval.run_m1_metrics                    # record-only metric table

# Frontend
cd frontend && npm run build && npx ng test --watch=false --browsers=ChromeHeadless   # 15 specs

# Live smokes (stack + creds required)
./scripts/m1_p1_smoke.sh        # /section happy + preflight 422
./scripts/m1_p3_smoke.sh        # /batch fan-out (+ resume when interrupted)
./scripts/m1_p4_critic_smoke.sh # /critic fixture warnings
./scripts/m1_e2e_smoke.sh       # Phases 1-4 in one run
```

Endpoint-level curls: design-reference §16 (`/section`, `/section/resume`, `/section/abandon`), §18.12.3 (`/batch`, `/batch/resume`), §18.10 (`/critic`).

LangSmith trace shapes: [`langsmith-trace-reference.md`](./langsmith-trace-reference.md).

## 5. Phase 1.5 / M3 trigger list

| Trigger | Where it lands |
|---|---|
| Flip the 7 record-only eval metrics to CI-gating (after first baseline) | `.github/workflows/rag-eval-gate.yml` M1-metrics step + `eval/run_m1_metrics.py` |
| Critic hard-fail surface (`blocks_submit=True`) after precision baseline | `app/api/critic.py::clamp_phase1` + ADR |
| CO-of-record binding on `/resume` (any same-tenant CO can resume today) | `app/api/resume.py` D8.1 note |
| Hard-delete of swept checkpoints (sweeper marks, never deletes) | `app/sweeper.py` |
| Nova Micro LLM-as-judge inside QueryGuardrails | `app/guardrails.py` (M2 handoff §5.3) |
| Audit-reader endpoint exposing `tool_calls[]` | M2 handoff §5.4 |
| Section J attachment storage + 4th critic tool | ADR-0012 carve-out |
| Streaming UX via `agent.stream()` | design ref §17 |
| LangSmith redaction env vars when corpus exceeds public-domain FAR | design ref §17 |
| Part II clause-matrix expansion beyond trainer set-asides/types | `docs/reference/far/clause_applicability.json` |

## 6. Known deviations from the per-phase specs

- Single integration branch (`cj/m1-langchain-integration`) instead of the per-PR branch fan-out — single-session implementation; PR-level gates were run as local test gates instead.
- Schema round-trip tests live in one parametrized module (`tests/agents/schemas/`) rather than per-model files — same coverage (35 models).
- Frontend karma stack + `test` target added (repo previously had no runner); `tsconfig.app.json` now excludes `*.spec.ts`.
- Coordinator interrupt protocol adapted to langgraph 1.x: children RETURN `__interrupt__` (no GraphInterrupt raise); parent nodes call `interrupt()` themselves with replay-safe child-state detection (phase 3 spec §10 has details).

## 7. Next-session pickup checklist (written 2026-06-12)

**Git state at handoff:** `cj/m1-langchain-integration` @ `4437bc7`, 12 commits ahead of `main` (base `f476e36`). Working tree clean except untracked session tooling (`.agents/`, `.claude/`, `.githooks/`, `skills-lock.json`) — not M1 work; leave them.

Work through in order; stop anywhere — each step is independently committable.

### 7.1 Live verification (the only unchecked exit-gate boxes)

Everything below is code-complete but never run against the live stack. Needs: `docker-compose -f infra/docker/docker-compose.yml up --build`, seeded corpus (M2 baseline), `AWS_BEARER_TOKEN_BEDROCK` set in the repo-root env file (template: `.env.example`).

```bash
cd services/ai-orchestrator
# 1. Mongo-gated tests stop auto-skipping once atlas-local is up:
python -m pytest tests/agents/test_checkpointer.py tests/api/test_pause_restart.py -v
# 2. Smokes, in dependency order:
./scripts/m1_p1_smoke.sh          # /section happy path + preflight 422
./scripts/m1_p3_smoke.sh          # /batch fan-out (+ resume when interrupted)
./scripts/m1_p4_critic_smoke.sh   # /critic fixture warnings
./scripts/m1_p4_batch_critic_smoke.sh
./scripts/m1_e2e_smoke.sh         # Phases 1-4 in one run + audit join check
# 3. LangSmith span order (LANGSMITH_TRACING=true + LANGSMITH_API_KEY):
#    verify against langsmith-trace-reference.md — part_i/part_iv parallel
#    siblings; critic AFTER aggregate; no draft before gate.
```

Then tick the corresponding tracker §4 exit-gate boxes (P1: live `draft_returned` + LangSmith run name; P2: container-restart resume; P3: parallel-sibling spans; P4: critic-after-aggregate span; P5: e2e smoke) — one `docs(tracker)` commit.

**Likely first failures to expect:**
- `/section` live run depends on the M2 seeded corpus producing rerank scores ≥ 0.55 — lean-corpus L/M sections may interrupt or withhold. That is correct gate behavior, not a bug; use `/section/resume` (or the wizard panel) to complete.
- `/resume` tenant check reads `snapshot.metadata.tenant_id` — verify langgraph actually persists invoke-config metadata into checkpoint metadata on the live MongoDBSaver. If absent, the check falls open (documented in phase-2 spec §10) and needs a fix before declaring ADR-0012 D8.1 done.

### 7.2 Merge / PR

- Target branch decision is OPEN: `main` (repo PR convention) vs. stacking on `cj/m2-integration` (where the 21 M2 PRs live unmerged). Check `git branch -a` + ask the user before opening anything.
- A PR will trigger: `rag-eval-gate` (now path-matches `app/agents/**` + `app/api/**`; req_aid_1 + record-only metric steps run without creds), `debt-enforcement` (no lockfile changes made — passes clean), `pr-summary-check`.
- PR-template debt checkbox: the NO branch (no locked items touched).

### 7.3 Known loose ends (small, non-blocking)

- `eval/run_m1_metrics.py` agent-run metrics read `eval/results/m1_agent_runs.jsonl` — no harvester writes that file yet. Phase 1.5 candidate: extract run records from audit rows (`generation.tool_calls`) or a LangSmith export.
- Frontend bundle grew 471 → 498.6 kB across M1 (reactive forms + batch/critic UI). Within reason; relevant if anyone re-checks the F1 ±10 kB guideline.
- `solicitation.service.ts` `useMockAI` flipped to `false` — the wizard now requires gateway + orchestrator up; backend-less demo needs `svc.useMockAI = true` from the browser console.
- Per-PR branch flow was collapsed into the single integration branch; if the instructor workflow needs the 27-PR shape, cherry-pick by commit (each phase = one feat commit + one tracker commit).

### 7.4 Fast context reload (cold session)

1. Read this file top to bottom (~3 min).
2. `git log --oneline f476e36..HEAD` — 13 commits: 6 feat + 6 tracker (one pair per phase) + this handoff update.
3. Only if touching a specific subsystem: that phase spec's §10 handoff notes, then the design-reference section it cites.
4. Memory file `project_m1_agentic_design.md` mirrors this state.
