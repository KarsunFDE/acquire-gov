# M1 · Phase 5 — Hardening + observability

**Type:** non-vertical. Eval-gate metric collection (record-only Phase 1), e2e smoke covering Phases 1–4, `req_aid_1` test marker coverage, M1 close-out handoff doc. End state: M1 is shippable; baseline metrics measured for Phase 1.5 trigger decisions.

**Status:** see [`m1-agentic-drafting/tracker.md`](../tracker.md) §1.

**Design reference:** [`m1-agentic-drafting/design-reference.md`](../design-reference.md) §13.2 + §18.8 (eval-gate metrics — record-only per ADR-0015 fix).

---

## 1. Goal

Prove M1 is shippable end-to-end with all four ADRs implemented. Land eval-gate metric collection (record-only — no CI fail thresholds in Phase 1). Write the M1 close-out handoff doc so Phase 1.5 / M3 sessions have a clean pickup point.

## 2. In scope

- 7 eval-gate metrics emit measurements into the eval-gate run summary:
  - `tool_order_drift` (ADR-0013 §13.2)
  - `withhold_short_circuit_rate` (same)
  - `hitl_interrupt_recall` (same)
  - `critic_l_m_alignment_recall` (ADR-0014 §18.8)
  - `critic_set_aside_recall` (same)
  - `critic_clin_recall` (same)
  - `critic_false_positive_rate` (same)
  - Phase 1: ALL record-only; no CI thresholds. Phase 1.5 PR after baseline measurement flips to gating.
- `req_aid_1` pytest marker has ≥ 3 tests asserting structured-output contract on `/section`, `/batch`, `/critic`.
- `req_rag_3` count holds at 13+ (no regression).
- Single E2E smoke run that exercises Phases 1–4: clean atlas-local + seeded corpus + real Bedrock → Step 1 form → /batch with all 4 sections null → resume any interrupt → Step 12 critic → Step 13 publish modal.
- LangSmith trace verification doc: what good traces look like for `/section`, `/batch`, `/critic`.
- M1 close-out section added to `m2-grounded-retrieval/handoff.md` (or new `docs/specs/m1-handoff.md`).

## 3. Out of scope

- Phase 1.5 metric-threshold flip (separate ADR / spec).
- Audit-reader endpoint exposing `tool_calls` (M3 territory per ADR-0012 carve-out).
- LangSmith input/output redaction env vars (Phase 1.5 trigger when corpus expands beyond synthetic).
- Section J file-persistence backend (M3).

## 4. Dependencies

- Phases 1–4 all completed (or at least Phase 1 + Phase 4 standalone-path for the smaller smoke variant).
- Eval fixture set: 20 synthetic solicitations with known L↔M mismatches injected, 20 known-good (per §18.8). May land partially before Phase 5 — fixtures themselves are a Phase 0 or Phase 4 dependency.

## 5. PR breakdown + parallelism

```
[Phases 1-4 done]
   │
   ├── P5.1 eval metric impls ─────┐
   ├── P5.2 req_aid_1 tests ───────┤
   │                               ├─ converge → P5.4 close-out handoff
   ├── P5.3 e2e smoke + LangSmith ─┘
```

| PR | Branch | What lands | Parallel-after | Sequential-before |
|---|---|---|---|---|
| P5.1 | `cj/m1-p5-eval-metrics` | 7 eval-metric measurements; eval-gate workflow extension to emit them into run summary; thresholds NOT set | Phase 4 | P5.4 |
| P5.2 | `cj/m1-p5-req-aid-1` | Tests under `req_aid_1` marker asserting structured-output contract on each endpoint | Phase 4 | P5.4 |
| P5.3 | `cj/m1-p5-e2e-smoke` | End-to-end script + LangSmith trace verification doc | Phase 4 | P5.4 |
| P5.4 | `cj/m1-p5-handoff` | M1 close-out section in handoff doc | P5.1 + P5.2 + P5.3 | — |

All three pre-handoff PRs (P5.1, P5.2, P5.3) can run in parallel.

## 6. Task checklist

### P5.1 — Eval metrics (record-only)

- [x] `services/ai-orchestrator/eval/metrics/tool_order_drift.py` — Levenshtein distance against the prompted tool-order sequence; computed per run from agent message history.
- [x] `eval/metrics/withhold_short_circuit_rate.py` — per-run: gate=withhold AND draft_section_text in tool_calls → failure; emit rate.
- [x] `eval/metrics/hitl_interrupt_recall.py` — per-run: score in hitl band AND run not interrupted → failure; emit recall (target =1.00 in Phase 1.5).
- [x] `eval/metrics/critic_l_m_recall.py` — fixture set with known L↔M misalignments injected; measure recall.
- [x] `eval/metrics/critic_set_aside_recall.py` — same shape.
- [x] `eval/metrics/critic_clin_recall.py` — same shape.
- [x] `eval/metrics/critic_false_positive_rate.py` — 20 known-good fixtures; measure % producing overall_severity ≥ warn.
- [x] `.github/workflows/rag-eval-gate.yml` extension: emit all 7 metrics into the run summary (`$GITHUB_STEP_SUMMARY`). NO CI fail thresholds; comment in the workflow flags the Phase 1.5 trigger.

### P5.2 — req_aid_1 marker

- [x] `tests/test_req_aid_1_structured_output.py`:
  - `test_section_response_is_pydantic_validated` — POST /section → response.json() parses as `FinalDraftSection.model_validate(...)`.
  - `test_batch_response_is_pydantic_validated` — POST /batch → response.json() parses as `SolicitationDraftBundle.model_validate(...)`.
  - `test_critic_response_is_pydantic_validated` — POST /critic → response.json() parses as `ConsistencyReport.model_validate(...)`.
- [x] CI workflow runs `pytest -m req_aid_1` alongside `req_rag_3` on every PR.

### P5.3 — E2E smoke + LangSmith trace doc

- [x] `services/ai-orchestrator/scripts/m1_e2e_smoke.sh` — exercises:
  1. Clean atlas-local restart (drops collections).
  2. `make seed` to load FAR snapshot + synthetic solicitations.
  3. POST /draft-solicitation/batch with all 4 sections null.
  4. If response is batch_interrupted, POST /batch/resume to approve.
  5. POST /critic.
  6. Verify all responses parse + audit rows joined on shared run_ids.
- [x] `docs/specs/m1-langsmith-trace-reference.md` — screenshots / span-tree examples for the three endpoints' canonical traces.

### P5.4 — M1 close-out handoff

- [x] Add a new section to `docs/specs/m2-grounded-retrieval/handoff.md` (or write `docs/specs/m1-handoff.md`):
  - Phase status snapshot from tracker §1.
  - Final architecture summary (1 paragraph).
  - Known Phase 1.5 triggers list (eval thresholds flip, Nova-Micro guardrails wiring, audit-reader endpoint, Section J storage, etc.).
  - Verification one-liners for `/section`, `/batch`, `/batch/resume`, `/critic`, `/section/resume`, `/section/abandon`.
  - LangSmith trace examples for canonical paths.
- [x] Update memory file `project_m1_agentic_design.md` with M1 completion state.

## 7. In-progress checklist

1. `git log cj/m1-p5-* --oneline`.
2. §6 first unchecked.
3. Verify Phases 1–4 are all `completed` in tracker §1 before P5.4.
4. Tracker §2 "Next" sentence.

## 8. Phase 5 exit gate

See tracker §4 Phase 5.

## 9. Handoff notes

**2026-06-11 (Phase 5 complete on `cj/m1-langchain-integration`):**

- 7 metric modules landed under `eval/metrics/` (3 agent-run + 4 critic) with a fixture set (`eval/fixtures/m1_critic_fixtures.jsonl`, 40 rows from `eval/build_m1_fixtures.py`). Offline run: set_aside recall 1.00 (8), clin recall 1.00 (6), false-positive 0.00 (20); agent-run metrics + L↔M recall record null until a live runs file / Bedrock creds exist — no silent zeros.
- Metric layout deviates from the per-file naming in §6 (grouped as agent_run_metrics.py + critic_metrics.py) — same 7 metrics, fewer files.
- rag-eval-gate.yml: req_aid_1 step + record-only metrics step (always exit 0) + path triggers extended to app/agents/** + app/api/**.
- LangSmith doc is span-tree reference text (no screenshots — needs a live traced run; placeholder noted in langsmith-trace-reference.md).
- e2e smoke (`scripts/m1_e2e_smoke.sh`) NOT yet executed against a live stack this session — run before declaring the tracker §4 P5 smoke box verified.
- Close-out: `docs/specs/m1-agentic-drafting/handoff.md` (new m1 handoff; m2 handoff untouched).
