# M1 Agentic Drafting — Implementation Tracker

**Live state document.** This file is the entry point for any session resuming M1 implementation work. It tracks phase status, names the current vertical slice in flight, and points at the per-phase spec the implementer follows. Update this file at every phase status transition (commit message: `docs(tracker): phase N → <status>`).

Decisions: [ADR-0012](../../adrs/0012-agentic-draft-solicitation-workflow.md) · [ADR-0013](../../adrs/0013-multi-agent-coordinator-and-critic.md) · [ADR-0014](../../adrs/0014-per-far-part-batch-fan-out.md) · [ADR-0015](../../adrs/0015-preflight-input-validation.md)

Design reference: [`m1-agentic-drafting/design-reference.md`](./design-reference.md) (endpoint contracts, schemas, tool internals, audit shape — read for the *what*, not for implementation order)

---

## 1. Phase status

| # | Title                              | Status      | Started    | Completed | Branch           | Vertical slice? |
|---|------------------------------------|-------------|------------|-----------|------------------|-----------------|
| 0 | Foundation                         | completed   | 2026-06-11 | 2026-06-11 | cj/m1-langchain-integration | no (backend-only setup) |
| 1 | Single-section happy path          | completed   | 2026-06-11 | 2026-06-11 | cj/m1-langchain-integration | **yes** — CO clicks AI-draft Section C, sees grounded draft + citations |
| 2 | HITL interrupt + resume + abandon  | completed   | 2026-06-11 | 2026-06-11 | cj/m1-langchain-integration | **yes** — low-confidence draft pauses; CO resumes; completes |
| 3 | Batch coordinator (per-AI-Part)    | completed   | 2026-06-11 | 2026-06-11 | cj/m1-langchain-integration | **yes** — CO clicks "Draft AI Parts"; 4 sections + Part II clauses + Part III metadata in one response |
| 4 | Consistency critic                 | not_started | —          | —         | —                | **yes** — Step 12 critic warnings render before submit |
| 5 | Hardening + observability          | not_started | —          | —         | —                | no (eval metrics + smoke + req_aid_1) |

**Status values**: `not_started` → `in_progress` → `gate_review` → `completed`. `blocked` is also valid; if used, populate the "Notes" column with the blocker.

---

## 2. Active phase

(empty when no phase is in_progress)

When a phase enters `in_progress`, populate this section with:

- Phase number + title
- Current PR being worked on
- Last-commit SHA on the branch
- Any unresolved blocker
- Next concrete action (one sentence)

Example (when populated):

```
Active: Phase 1 · PR P1.4 (build_section_drafter_agent + handler rewrite)
Branch: cj/m1-p1-handler · last commit deadbeef
Blocker: none
Next: open PR with the handler + integration test against stubbed Bedrock
```

---

## 3. Crash-recovery checklist (start-of-session for resuming work)

Read in this order. Stop as soon as you have enough context to take the next action.

1. **This tracker file**, §1 phase status table — find the lowest-numbered non-`completed` phase.
2. **This tracker file**, §2 active phase block — if populated, that is your entry point.
3. **The phase spec for the active phase** (`docs/specs/m1-phase-N-*.md`) — find the "In-progress checklist" section near the bottom.
4. **`git log cj/m1-pN-* --oneline | head -10`** — what actually merged vs. what the tracker thinks. Trust git over the tracker on conflict; reconcile by updating the tracker.
5. **Only if scope question arises**: read the relevant ADR (0012–0015).
6. **Only if endpoint-shape question arises**: read `m1-agentic-drafting/design-reference.md` (design reference).

If §2 active-phase block is empty but §1 shows a phase `in_progress`, the tracker drift is the bug to fix first.

---

## 4. Phase summaries (one block per phase)

Each block names the vertical slice (if any), the gate that proves done, and links to the per-phase spec with the full PR list. Detailed task checklists live in the per-phase docs, not here — this tracker stays scannable.

### Phase 0 — Foundation

**Type:** backend-only setup (no vertical slice). All schemas, config, checkpointer, test markers in one place so subsequent phases can reach for them without churn.

**Spec:** [`m1-agentic-drafting/phases/0-foundation.md`](./phases/0-foundation.md)

**Exit gate (every box must be checked before Phase 1 starts):**
- [ ] `app/agents/schemas.py` defines every Pydantic model named across ADR-0012/0013/0014/0015 (`SectionPlanContext`, `RetrievedEvidence`, `RelatedSolicitations`, `ExtractedRequirements`, `SectionDraftSkeleton`, `ValidationResult`, `GateDecisionResult`, `FinalDraftSection`, `Citation`, `ClaimCitation`, `PendingToolCall`, `PartDraftBundle`, `PartIIClauseList`, `PartIIIAttachmentMeta`, `PartResult`, `FARClauseReference`, `ConsistencyReport` + sub-reports, `BatchDraftRequest`, `BatchResumeRequest`, `SolicitationDraftBundle`, `PreflightResult`).
- [ ] `app/config.py` reads `BEDROCK_EXTRACT_MODEL`, `BEDROCK_CRITIC_MODEL`, `GATE_PASS_THRESHOLD`, `GATE_WITHHOLD_THRESHOLD`, `AGENT_CHECKPOINT_*`, `AGENT_ORPHAN_*`, `MAX_BATCH_FAN_OUT`, `LANGSMITH_*`, `SET_ASIDE_STRICT_EXTRA` knobs.
- [ ] `app/agents/checkpointer.py::build_mongodb_saver()` returns an `lru_cache`d `MongoDBSaver`; `thread_id_for(...)` + `parse_thread_id(...)` helpers live there.
- [ ] `.env.example` lists every new env var with a one-line comment.
- [ ] `pytest -q services/ai-orchestrator/tests/agents/schemas/ -v` passes (Pydantic field validators round-trip for every model).
- [ ] `pytest -m req_rag_3` still passes (no regression from ADR-0012 baseline).
- [ ] Tracker §1 status row for Phase 0 updated to `completed`.

**PR count:** 3 (P0.1 schemas, P0.2 config + env, P0.3 checkpointer + tests).

**Within-phase parallelism:** P0.1 must land first (later PRs import from it); P0.2 + P0.3 can run in parallel after P0.1.

### Phase 1 — Single-section happy path (vertical slice)

**Vertical slice:** CO opens wizard → fills Step 1 form (reactive forms validate) → clicks "AI-draft Section C" → backend runs preflight + agent → response carries `outcome="draft_returned"` + 5 citations + `gate_decision="pass"` → wizard renders draft text + provenance badge + citation list. Real Bedrock + seeded FAR corpus.

**Spec:** [`m1-agentic-drafting/phases/1-single-section.md`](./phases/1-single-section.md)

**Exit gate:**
- [ ] `POST /draft-solicitation/section` with full Step 1 metadata + section_id=C returns 200 with `outcome="draft_returned"` against the seeded FAR corpus + atlas-local Mongo + real Bedrock (`AWS_BEARER_TOKEN_BEDROCK` set).
- [ ] Wizard Step 1 form blocks Next button when any of {title, agency_id, naics, set_aside, contract_type} is empty.
- [ ] section-card "AI-draft Section C" button is disabled when Step 1 form is invalid (`[step1Ready]="false"`).
- [ ] section-card renders the response: section_text in textarea, provenance badge `ai`, gate badge `Grounded ✓`, citation list with chunk_id + far_clause + relevance_score.
- [ ] Audit row written with `action="retrieval_and_generate"` + `outcome="draft_returned"` + `preflight.ready=true` + `tool_calls[]` non-empty.
- [ ] LangSmith run name `section_drafter` visible in trace UI when `LANGSMITH_TRACING=true`.
- [ ] `pytest -m req_rag_3` still passes (12+ tests).
- [ ] `req_aid_1` marker tests pass (response is Pydantic-validated `FinalDraftSection`).

**PR count:** 7 (preflight, 4 programmatic tools, 2 LLM tools, agent builder, handler, Step 1 reactive forms, section-card binding).

**Within-phase parallelism:** see [`m1-agentic-drafting/phases/1-single-section.md`](./phases/1-single-section.md) §4 for the dependency graph.

### Phase 2 — HITL interrupt + resume + abandon (vertical slice)

**Vertical slice:** CO clicks AI-draft Section L → low rerank score (lean corpus) → middleware interrupts before `draft_section_text` runs → handler returns `outcome="interrupted"` + pending_tool_call → section-card renders "Pending CO decision" panel → CO clicks Approve → POST /section/resume → agent resumes → draft completes with `outcome="draft_returned"`. Multi-day pause survives an uvicorn restart.

**Spec:** [`m1-agentic-drafting/phases/2-hitl-resume.md`](./phases/2-hitl-resume.md)

**Exit gate:**
- [ ] Forcing `rerank_top_score=0.45` (hitl band) produces `outcome="interrupted"` + pending_tool_call in response.
- [ ] `POST /section/resume` with `decision="approve"` resumes the run and returns `outcome="draft_returned"`.
- [ ] `POST /section/resume` with `decision="reject"` resumes and returns `outcome="withheld"`.
- [ ] Checkpoint state in `agent_checkpoints` collection survives a container restart; resume after restart completes successfully.
- [ ] `POST /section/abandon` marks the checkpoint `abandoned=true`; sweeper picks up after `AGENT_ORPHAN_AGE_DAYS` (force-clock test).
- [ ] section-card renders "Pending CO decision" panel with 3 buttons; clicking Approve sends the resume POST and re-renders on completion.
- [ ] Audit rows joined on `run_id`: original draft row + agent_resume row.

**PR count:** 4 (middleware, /resume handler, /abandon handler + sweeper, frontend interrupt surface).

### Phase 3 — Batch coordinator with per-AI-Part fan-out (vertical slice)

**Vertical slice:** CO fills Step 1 → clicks "Draft AI Parts" → backend coordinator fans out to PartIDrafter (drafts C+H) + PartIVDrafter (drafts L+M) in parallel via `Send` + resolves Part II clauses programmatically + passes through Part III attachment metadata → aggregates → consistency critic runs → response is `SolicitationDraftBundle` with 4 PartResults + ConsistencyReport. Wizard renders all four sections + Part II clause list + Part III index.

**Spec:** [`m1-agentic-drafting/phases/3-batch-coordinator.md`](./phases/3-batch-coordinator.md)

**Exit gate:**
- [ ] `POST /batch` with all 4 AI-draftable section provenances null returns 200 with `overall_outcome="batch_completed"` and `parts.{I,II,III,IV}.kind` matching `{llm_drafted, programmatic_resolved, wizard_provided, llm_drafted}`.
- [ ] Forcing a hitl-band score on one Part → `overall_outcome="batch_interrupted"` + `pending_interrupts` length 1; non-interrupted Part keeps its draft.
- [ ] `POST /batch/resume` resumes the checkpointed coordinator state and completes.
- [ ] Section I list in `parts.II.sections.I.clauses_by_reference` matches the deterministic lookup for the given `(set_aside, contract_type, agency_supplement)`.
- [ ] Slowapi multi-cost: a batch of 4 sections costs 4 against the per-tenant rate budget; audit row records `batch.rate_limit_cost`.
- [ ] LangSmith trace shows `batch_coordinator_run` parent span with `part_i_drafter` + `part_iv_drafter` parallel siblings.
- [ ] Wizard "Draft AI Parts" button shows progress + per-Part HITL surfaces on interrupt.

**PR count:** 6 (Part II programmatic node, Part III passthrough node, multi-section tool variant, PartDrafterAgent factory, coordinator graph + endpoints, frontend batch button).

### Phase 4 — Consistency critic (vertical slice)

**Vertical slice:** At wizard Step 12 (Review), wizard POSTs `/draft-solicitation/critic` with current section bundle → critic agent runs verify_l_m_consistency (LLM) + check_set_aside_consistency (programmatic) + check_clin_coverage (programmatic) → response is `ConsistencyReport` → wizard renders inline warnings. Step 13 publish modal still gates on FAR 5.705 CO approval; critic never blocks submit (Phase 1 warn-only).

**Spec:** [`m1-agentic-drafting/phases/4-consistency-critic.md`](./phases/4-consistency-critic.md)

**Exit gate:**
- [ ] `POST /critic` with a known-mismatched L/M pair returns `ConsistencyReport` with `lm_alignment.overall_severity="warn"` and `mismatches` non-empty.
- [ ] Set-aside ↔ Section K mismatch (e.g., `set_aside=SDVOSB` + Section K missing `52.219-27`) → `set_aside_consistency.overall_severity="warn"`.
- [ ] CLIN missing in Section C → `clin_coverage.gaps` non-empty, gap-level `severity="warn"` (since 1 missing), `overall_severity="warn"`.
- [ ] `blocks_submit=False` regardless of severities (Phase 1 invariant).
- [ ] Wizard Step 12 renders the three sub-reports inline; Step 13 publish modal still fires regardless of severities.
- [ ] When critic invoked from the batch coordinator path, it runs AFTER aggregate (verified via LangSmith span order).

**PR count:** 4 (critic tools, critic agent builder, /critic endpoint, frontend Step 12 integration).

### Phase 5 — Hardening + observability

**Type:** non-vertical (eval metrics + smoke tests + req_aid_1 + documentation polish).

**Spec:** [`m1-agentic-drafting/phases/5-hardening.md`](./phases/5-hardening.md)

**Exit gate:**
- [ ] Four new eval-gate metrics (`tool_order_drift`, `withhold_short_circuit_rate`, `hitl_interrupt_recall`, `critic_*`) emit measurements into the eval-gate run summary (record-only — no CI fail).
- [ ] `req_aid_1` marker covers ≥ 3 tests asserting structured-output contract on `/section`, `/batch`, `/critic`.
- [ ] `req_rag_3` count holds at 13+ (no regression).
- [ ] End-to-end smoke: clean atlas-local + seeded corpus + real Bedrock + Step 1 → /batch → resume any interrupt → Step 12 critic → Step 13 publish modal — all green in one CLI run.
- [ ] M1 close-out section added to `m2-grounded-retrieval/handoff.md` (or new `m1-handoff.md`) for the next phase's session pickup.

**PR count:** 3 (eval metric collection, e2e smoke + req_aid_1, doc polish).

---

## 5. Cross-phase dependency graph

```
P0 ─── P1 ─── P2 ─── P3 ─── P4 ─── P5
        │           │
        └─ P4 (standalone-critic-only path is reachable after P1)
```

P4 has two valid entry points: after P3 (batch-path critic) or after P1 (standalone `/critic` endpoint only). Phase 4 doc enumerates both. If P3 slips, P4 can still start on the standalone path.

P5 nominally depends on all of P1-P4 but the eval-metric PRs can land incrementally as each upstream phase completes.

---

## 6. Status update protocol

When transitioning a phase, do this in one commit (per `m2-grounded-retrieval/rollout.md` per-PR style):

1. Open phase: edit Phase N row in §1 to `Status: in_progress`, `Started: <YYYY-MM-DD>`, `Branch: <branch-name>`. Populate §2 active-phase block.
2. Mid-phase PR landings: update the per-phase spec's task checklist (`docs/specs/m1-phase-N-*.md`). Tracker §2 "Next" line gets a fresh sentence. Do NOT update §1 mid-phase.
3. Close phase: §1 row → `Status: gate_review` first while running exit-gate checks. After all gate boxes pass, → `Status: completed`, `Completed: <YYYY-MM-DD>`. Clear §2 active-phase block.

Commit messages: `docs(tracker): phase N → in_progress` / `gate_review` / `completed`. One commit per transition, no batching.

---

## 7. Out-of-scope for this tracker

This document **does not** carry:

- Endpoint contracts (those are in `m1-agentic-drafting/design-reference.md`).
- Pydantic schema definitions (same).
- Tool internals or system prompts (same).
- Architectural rationale (those are in the ADRs).
- Day-by-day implementer log (use git log + per-phase task checklists).

If you're tempted to add any of the above here, push it into a per-phase spec or an ADR. The tracker stays scannable — under 350 lines is the target ceiling.
