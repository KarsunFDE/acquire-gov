# M1 · Phase 0 — Foundation

**Type:** backend-only setup. No vertical slice; no user-visible behavior changes. This phase pre-stages every Pydantic schema, config knob, and checkpointer wiring that Phases 1–5 reach for, so subsequent phases never block on schema churn.

**Status:** see [`m1-implementation-tracker.md`](./m1-implementation-tracker.md) §1.

**Design reference:** [`m1-agentic-draft-workflow.md`](./m1-agentic-draft-workflow.md) §6 (config), §6.2 (schemas), §10 (checkpointer).

---

## 1. Goal

Land every cross-phase Pydantic model, every env-var config knob, and the `MongoDBSaver` singleton in one cohesive set of PRs. After Phase 0, no later phase needs to invent or extend these.

## 2. In scope

- All Pydantic schemas defined by ADR-0012 D3, ADR-0013 D6.3, ADR-0014 D6 + D9, ADR-0015 D5 — in one module (`app/agents/schemas.py`).
- `app/config.py` extended with every new env knob (D2, D6 from each ADR).
- `app/agents/checkpointer.py` with the `MongoDBSaver` singleton factory + `thread_id` helpers.
- Pytest markers (`req_aid_1`) registered in `pytest.ini`.
- `.env.example` updates with every new env var + a one-line comment per.

## 3. Out of scope

- Tools (Phase 1).
- Agent builders (Phase 1 + 3 + 4).
- Endpoints / handlers (Phase 1+).
- Frontend (Phase 1+).
- LangSmith — env vars only; the trace-emit code lives wherever the agent is constructed (Phase 1+).

## 4. Dependencies

- ADR-0012, ADR-0013, ADR-0014, ADR-0015 all merged.
- Atlas-local Mongo running (so checkpointer wiring can connect at test time).
- M2 baseline branch (`cj/m2-integration` HEAD).

## 5. PR breakdown + parallelism

```
       ┌── P0.1 ──┬── P0.2 ──┐
       │ schemas  │  config  │
START ─┤          ├          ├─ Phase 0 complete
       │          │ P0.3     │
       │          │ checkpr  │
       └──────────┴──────────┘
```

P0.1 must land first (P0.2 + P0.3 import schemas). P0.2 and P0.3 can run in parallel branches once P0.1 is in.

| PR | Branch | What lands | Gates |
|---|---|---|---|
| P0.1 | `cj/m1-p0-schemas` | `app/agents/schemas.py` defining every Pydantic model + sub-model + per-model unit tests; `pytest.ini` adds `req_aid_1` marker | `pytest services/ai-orchestrator/tests/agents/schemas/ -v` all green; `req_rag_3` regression passes |
| P0.2 | `cj/m1-p0-config` | `app/config.py` reads new env knobs; `.env.example` documents each | `python -c "from app import config; assert all(hasattr(config, k) for k in [...])"` green |
| P0.3 | `cj/m1-p0-checkpointer` | `app/agents/checkpointer.py` with `build_mongodb_saver()` + `thread_id_for()` + `parse_thread_id()`; integration test against atlas-local writes + reads back a checkpoint | unit + integration test green; new collections `agent_checkpoints` + `agent_checkpoint_writes` appear in Mongo |

## 6. Task checklist

Update inline as PRs land. Mark `[x]` after merge to `cj/m2-integration` (or whichever integration branch we use for the M1 rollout).

### P0.1 — Schemas

- [ ] Create `services/ai-orchestrator/app/agents/__init__.py`.
- [ ] Create `services/ai-orchestrator/app/agents/schemas.py` containing every model named in tracker §4 Phase 0 exit gate.
- [ ] Every model uses `model_config = ConfigDict(extra="forbid")` (per spec §6.2 invariant).
- [ ] Every `Literal` enum matches its ADR source exactly (section_id ∈ `{A,B,C,D,E,F,G,H,J,K,L,M}` — no I — per ADR-0012 D3).
- [ ] Add `tests/agents/schemas/test_*_round_trip.py` per model: serialize → deserialize → equality.
- [ ] Add unknown-field rejection tests (extra='forbid' enforced).
- [ ] Update `services/ai-orchestrator/pytest.ini` to register `req_aid_1` marker.
- [ ] Run `pytest services/ai-orchestrator/tests/ -q` — all M2 tests + new schema tests pass.

### P0.2 — Config

- [ ] Extend `app/config.py` with all knobs from the design reference §6 (ADR-0012) + §18.6 (ADR-0013/0014) + §19 (ADR-0015).
- [ ] Required new knobs:
  - `BEDROCK_EXTRACT_MODEL` (default `amazon.nova-lite-v1:0`)
  - `BEDROCK_CRITIC_MODEL` (default `amazon.nova-lite-v1:0`)
  - `BEDROCK_EXTRACT_MAX_RETRIES` (default 1)
  - `GATE_PASS_THRESHOLD` (default 0.55)
  - `GATE_WITHHOLD_THRESHOLD` (default 0.40)
  - `AGENT_CHECKPOINT_COLLECTION` (default `agent_checkpoints`)
  - `AGENT_CHECKPOINT_WRITES_COLLECTION` (default `agent_checkpoint_writes`)
  - `AGENT_CHECKPOINT_TTL` (Python `None` literal, not env-readable)
  - `AGENT_ORPHAN_SWEEP_INTERVAL_SECONDS` (default 3600)
  - `AGENT_ORPHAN_AGE_DAYS` (default 30)
  - `MAX_BATCH_FAN_OUT` (default 2)
  - `SET_ASIDE_STRICT_EXTRA` (default False)
  - `LANGSMITH_TRACING` (default False)
  - `LANGSMITH_API_KEY` (default None)
  - `LANGSMITH_PROJECT` (default `acquire-gov-m1-draft`)
- [ ] Update `.env.example` with every new key + a one-line comment.
- [ ] Add `tests/test_config_knobs.py` — assert every new attr is reachable on `config` module and has the documented default.

### P0.3 — Checkpointer

- [ ] Create `services/ai-orchestrator/app/agents/checkpointer.py`:
  - `build_mongodb_saver()` — `lru_cache(maxsize=1)`d factory.
  - `thread_id_for(*, solicitation_id, section_id, request_id)` — pure helper.
  - `parse_thread_id(thread_id)` — inverse; raises on malformed.
- [ ] Add `tests/agents/test_checkpointer.py` — integration test against atlas-local: write a checkpoint, read it back, verify TTL=None.
- [ ] Verify `agent_checkpoints` + `agent_checkpoint_writes` collections exist after the test.

## 7. In-progress checklist (crash recovery — what to do mid-phase)

Read these in order if you're picking up Phase 0 mid-stream:

1. `git log --oneline cj/m2-integration ^cj/m2-integration~30 | grep "p0-"` — what's already landed.
2. Open this file's §6 — find the first unchecked box.
3. Open the relevant PR branch (`cj/m1-p0-schemas` / etc.) — verify the branch is up to date with `cj/m2-integration`.
4. Re-read the PR's gate line in §5 — that's the proof-of-done bar.

## 8. Phase 0 exit gate

All boxes in tracker §4 Phase 0 exit gate must be checked. Specifically:

- [ ] All P0.1 + P0.2 + P0.3 task boxes (§6 above) green.
- [ ] `pytest services/ai-orchestrator/tests/agents/schemas/ -v` exits 0.
- [ ] `pytest -m req_rag_3` still passes (12+).
- [ ] `pytest -q services/ai-orchestrator/tests/` baseline test count not regressed.
- [ ] Tracker §1 Phase 0 row → `completed` (separate commit per `m2-rollout.md` style).

## 9. Handoff notes

Free-form section. Write here when the session ends mid-phase. Next session reads this before §7.

(empty)
