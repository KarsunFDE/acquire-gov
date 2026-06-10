# M1 · Phase 2 — HITL interrupt + resume + abandon

**Type:** vertical slice (UI + API). End state: low-confidence draft pauses the agent; CO sees a "Pending CO decision" panel and resumes with approve/edit/reject. Multi-day pause survives an uvicorn restart.

**Status:** see [`m1-agentic-drafting/tracker.md`](../tracker.md) §1.

**Design reference:** [`m1-agentic-drafting/design-reference.md`](../design-reference.md) §4.2 (/resume), §4.3 (/abandon), §9.1 (HITL middleware), §12.2 (interrupt flow), §6.3 (sweeper).

---

## 1. Goal

Light up the HITL middleware predicate written in Phase 1 (stubbed-False there) so it actually interrupts on the hitl-band rerank score. Add `/resume` + `/abandon` endpoints + the orphan-thread sweeper. Frontend renders the interrupt surface and resume decisions.

## 2. Vertical slice

```
CO clicks "AI-draft Section L" on a lean-corpus solicitation
  → POST /draft-solicitation/section
  → agent.retrieve_far_clauses returns chunks with rerank_top_score=0.45
  → agent calls compute_gate_decision(rerank_top_score=0.45)
  → middleware predicate: 0.40 <= 0.45 < 0.55 → INTERRUPT
  → MongoDBSaver persists state under thread_id
  → handler returns 200 with outcome="interrupted" + pending_tool_call
  → section-card renders "Pending CO decision" panel:
     [ Approve ]  [ Edit constraints ]  [ Reject ]
  → CO clicks Approve
  → POST /draft-solicitation/section/resume {run_id, decision="approve"}
  → handler reads checkpoint → Command(resume={"decisions":[{"type":"approve"}]})
  → agent resumes; gate tool re-runs with approved marker
  → draft_section_text runs; validate_citations passes
  → response: outcome="draft_returned" with section_text + citations
  → section-card renders draft + provenance=ai
```

Plus the abandon flow:

```
CO refreshes wizard mid-interrupt; new run_id preserved in SectionAudit.
CO decides "I'll type Section L by hand" instead.
  → section-card "Discard AI-draft" button
  → POST /draft-solicitation/section/abandon {run_id}
  → handler marks checkpoint abandoned=True; writes agent_abandon audit row
  → section-card reverts to empty-section human-typing
  → background sweeper reclaims the checkpoint after AGENT_ORPHAN_AGE_DAYS
```

## 3. In scope

- HITL middleware predicate fire-rule (light up from Phase 1 stub).
- `POST /draft-solicitation/section/resume` handler (ADR-0012 D8 spec §4.2).
- `POST /draft-solicitation/section/abandon` handler (ADR-0012 D8.2 spec §4.3).
- `app/sweeper.py` background asyncio task + `app/main.py` lifespan registration.
- Audit rows for `agent_resume` + `agent_abandon` + `agent_orphan_swept`.
- Frontend "Pending CO decision" panel in section-card with 3 buttons.
- Frontend "Discard AI-draft" button → `/abandon` POST.
- `solicitation.service.ts` gains `resumeSection()` + `abandonSection()` methods.
- `SectionAudit` interface gains `runId` field; persisted in component state.
- Multi-day pause integration test (kill container mid-interrupt + restart + resume).

## 4. Out of scope

- Batch coordinator (Phase 3) — `/batch/resume` is its own endpoint and lives there.
- Critic (Phase 4).
- Hardening (Phase 5).
- Resume authorization beyond same-tenant CO role (ADR-0012 D8.1 — Phase 1.5 / M3).

## 5. Dependencies

- Phase 1 completed (single-section happy path proven end-to-end).
- HITL middleware module exists from Phase 1 PR P1.4 (predicate stubbed False; this phase lights it up).
- Atlas-local Mongo + the `agent_checkpoints` + `agent_checkpoint_writes` collections (Phase 0 P0.3).

## 6. PR breakdown + parallelism

```
[P1 done]
   │
   ├── P2.1 middleware fire-rule ────┐
   ├── P2.2 /resume endpoint ────────┤
   ├── P2.3 /abandon + sweeper ──────┤
   │                                 ├─ converge → P2.5 e2e + multi-day-pause test
   ├── P2.4 frontend interrupt UI ───┘
```

| PR | Branch | What lands | Parallel-after | Sequential-before |
|---|---|---|---|---|
| P2.1 | `cj/m1-p2-middleware-fire` | Update `app/agents/middleware/hitl_gate.py::_interrupt_on_hitl_band` to return True when score is in hitl band; integration test verifying interrupt with stubbed score 0.45 | P1 | P2.2 + P2.5 |
| P2.2 | `cj/m1-p2-resume` | `app/api/resume.py` with `POST /section/resume` handler; reads checkpoint via `MongoDBSaver`; emits `Command(resume=...)`; writes `agent_resume` audit row; integration test for approve/edit/reject decisions | P2.1 | P2.5 |
| P2.3 | `cj/m1-p2-abandon-sweeper` | `app/api/abandon.py` + `app/sweeper.py` + lifespan registration in `app/main.py`; sweeper unit test with forced clock | P1 (independent of P2.1) | P2.5 |
| P2.4 | `cj/m1-p2-fe-interrupt` | section-card "Pending CO decision" panel render; resumeSection() + abandonSection() service methods; SectionAudit runId field; "Discard AI-draft" button | P1 | P2.5 |
| P2.5 | `cj/m1-p2-e2e-pause` | End-to-end smoke including container restart mid-interrupt → resume completes; multi-day-pause integration test | P2.1 + P2.2 + P2.3 + P2.4 | — |

P2.1 + P2.3 + P2.4 can start in parallel after Phase 1. P2.2 sequences after P2.1 (middleware must be firing before resume can be tested). P2.5 is the closing PR.

## 7. Task checklist

### P2.1 — Middleware fire-rule

- [ ] `app/agents/middleware/hitl_gate.py::_interrupt_on_hitl_band` now returns True for the hitl band per ADR-0012 D6.
- [ ] Add unit test fixtures for the three score bands: 0.0 (withhold, no interrupt), 0.45 (hitl, interrupt), 0.85 (pass, no interrupt), None (passthrough, no interrupt).
- [ ] Integration test: build SectionDrafterAgent + mock retriever returning score=0.45 + invoke → assert agent raises `GraphInterrupt` and the checkpoint exists in Mongo.
- [ ] `req_rag_3` regression still passes.

### P2.2 — /resume

- [ ] `app/api/resume.py` with `POST /draft-solicitation/section/resume` handler per spec §4.2.
- [ ] `ResumeSectionRequest` Pydantic — already in P0 schemas.
- [ ] Status codes: 200 success, 404 run_not_found, 403 tenant_mismatch, 409 run_not_paused, 422 edited_args_required.
- [ ] Audit row writer for `action="agent_resume"`.
- [ ] Integration tests: approve → draft_returned; edit → with edited rerank_top_score; reject → withheld.
- [ ] Mount route in `app/main.py`.

### P2.3 — /abandon + sweeper

- [ ] `app/api/abandon.py` with `POST /draft-solicitation/section/abandon` handler.
- [ ] Audit row writer for `action="agent_abandon"`.
- [ ] `app/sweeper.py` with `sweep_orphan_threads()` async function per spec §6.3.
- [ ] Wire sweeper into `app/main.py` lifespan startup task.
- [ ] Sweeper unit test using forced clock (`freezegun` or manual override).

### P2.4 — Frontend interrupt UI

- [ ] `frontend/src/app/models/solicitation.ts` — `SectionAudit` interface gains `runId?: string`.
- [ ] `solicitation.service.ts::resumeSection(runId, decision, editedArgs?, reason?)` per spec §12.5.
- [ ] `solicitation.service.ts::abandonSection(runId, reason?)` per spec §12.5.
- [ ] `section-card.component.ts` adds render branch for `lastResponse.outcome === "interrupted"`:
  - Renders pending_tool_call.reason as a yellow info banner.
  - 3 buttons: Approve / Edit / Reject.
  - Edit opens a small modal with editable args (Phase 1: just `rerank_top_score` slider).
  - On click → calls resumeSection() → re-renders on response.
- [ ] "Discard AI-draft" button visible on interrupt → calls abandonSection() → clears UI state.
- [ ] Unit tests via `*.component.spec.ts`.

### P2.5 — End-to-end pause + restart test

- [ ] Integration test in `tests/api/test_pause_restart.py`:
  - Force a score=0.45 → POST /section → interrupt response.
  - Capture run_id from response.
  - Restart the uvicorn process (or recreate the MongoDBSaver singleton).
  - POST /section/resume with the same run_id → assert it resumes from checkpoint and completes.
- [ ] Add to `m1-handoff.md` (or `m2-grounded-retrieval/handoff.md` if reusing): instructions to reproduce the pause-restart flow manually.

## 8. In-progress checklist (crash recovery)

1. `git log cj/m1-p2-* --oneline` — what's landed.
2. Check §7 — first unchecked box.
3. Verify P2.1 (middleware fire-rule) is landed before testing P2.2 (resume) — order matters.
4. Tracker §2 active-phase block "Next" sentence.

## 9. Phase 2 exit gate

See tracker §4 Phase 2.

## 10. Handoff notes

(empty)
