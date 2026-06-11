# M1 close-out handoff (P5.4)

**Date:** 2026-06-11 · **Branch:** `cj/m1-langchain-integration` · **Status:** all 6 phases completed (tracker §1).

Session pickup order for Phase 1.5 / M3 work: this file → [`tracker.md`](./tracker.md) §1 → the relevant phase spec's "Handoff notes" §10.

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
