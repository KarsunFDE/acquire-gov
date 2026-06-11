# M1 · Phase 1 — Single-section happy path

**Type:** vertical slice (UI + API). End state: CO clicks "AI-draft Section C" in the wizard with Step 1 completed, sees a grounded draft + citations rendered in section-card. Real Bedrock + seeded FAR corpus.

**Status:** see [`m1-agentic-drafting/tracker.md`](../tracker.md) §1.

**Design reference:** [`m1-agentic-drafting/design-reference.md`](../design-reference.md) §3–§13, §19 (preflight).

---

## 1. Goal

Wire ADR-0012's single-section agent end-to-end with ADR-0015's preflight gate and the wizard's reactive-forms migration. After this phase, the per-section AI-draft button delivers a grounded, cited draft for one section at a time.

## 2. Vertical slice (user-visible behavior at phase end)

```
CO opens new solicitation in wizard
  → Step 1 form (reactive forms; Next button disabled until valid)
    → fills title + agency_id + naics + set_aside + contract_type
    → optionally agency_supplement (Section L's degraded_context flag if missing)
    → Next
  → Steps 2–3 form fields (CLINs, A boilerplate)
  → Step 4 (Section C)
    → AI-draft button enabled (step1Ready=true)
    → click → POST /draft-solicitation/section
      → preflight passes → agent runs → grounded draft returned
    → section-card renders: section_text textarea + provenance="ai"
      + Grounded ✓ badge + 5 citations expandable + confidence dots
  → CO edits text → provenance → "ai-edited"
  → CO proceeds to next step
```

## 3. In scope

- Preflight handler stage (ADR-0015).
- Six tools: `retrieve_far_clauses`, `retrieve_related_solicitations`, `extract_section_requirements`, `compute_gate_decision`, `draft_section_text`, `validate_citations` (single-section variant).
- HITL middleware module **structurally present** but interrupt fire-rule is wired in Phase 2 — Phase 1 sets up the wiring but every gate decision returns `pass` against the seeded corpus.
- `build_section_drafter_agent()` factory.
- `POST /draft-solicitation/section` handler rewrite.
- Audit row writer with `tool_calls[]` sub-record.
- Frontend Step 1 → reactive forms migration with `Validators.required` on the 5 hard fields.
- `section-card.component.ts` receives `[step1Ready]` from parent + disables AI-draft button when invalid.
- `solicitation.service.ts::draftSection` payload extended with NAICS / set_aside / contract_type / agency_supplement.
- `degraded_context` warning banner in section-card.

## 4. Out of scope

- HITL interrupt-and-resume flow (Phase 2 — middleware structurally present but no interrupt fires in P1).
- `/abandon`, sweeper (Phase 2).
- Batch coordinator / Part agents (Phase 3).
- Consistency critic (Phase 4).
- Eval-gate metric measurements (Phase 5).

## 5. Dependencies

- Phase 0 completed (all schemas + config + checkpointer in place).
- Atlas-local Mongo running with seeded FAR corpus + 10 synthetic solicitations (M2 baseline).
- `AWS_BEARER_TOKEN_BEDROCK` set in `.env` for the smoke test; agent gracefully stubs without it (CLAUDE.md D-060).

## 6. PR breakdown + parallelism

```
[P0 done]
   │
   ├── P1.1 preflight ────────┐
   ├── P1.2 prog tools ───────┤
   ├── P1.3 LLM tools ────────┤
   │   (each tool can branch in parallel after P0)
   │                          ├─ converge ─→ P1.4 builder + handler ─→ P1.7 e2e smoke
   │                          │
   ├── P1.5 frontend forms ───┤
   ├── P1.6 frontend card ────┘
```

| PR | Branch | What lands | Parallel-after | Sequential-before |
|---|---|---|---|---|
| P1.1 | `cj/m1-p1-preflight` | `app/api/preflight.py` + unit tests for both `preflight_single_section` + `preflight_batch` | P0 | P1.4 |
| P1.2 | `cj/m1-p1-tools-prog` | 4 programmatic tools: `retrieve_far_clauses`, `retrieve_related_solicitations`, `compute_gate_decision`, `validate_citations` + per-tool unit tests + `req_rag_3` extension test | P0 | P1.4 |
| P1.3 | `cj/m1-p1-tools-llm` | 2 LLM tools: `extract_section_requirements` (Nova Lite via `with_structured_output`) + `draft_section_text` (Sonnet via `ChatBedrockConverse.with_structured_output`) + stubbed-LLM unit tests | P0 | P1.4 |
| P1.4 | `cj/m1-p1-builder-handler` | `app/agents/builder.py::build_section_drafter_agent()` + middleware module shell (predicate present but no interrupt yet) + `app/api/draft.py` handler rewrite + audit row extension with `tool_calls[]` | P1.1 + P1.2 + P1.3 | P1.7 |
| P1.5 | `cj/m1-p1-fe-step1-forms` | Wizard Step 1 → reactive forms migration + `Validators.required` + Next-button gate | P0 | P1.6 |
| P1.6 | `cj/m1-p1-fe-section-card` | `section-card.component` `[step1Ready]` input + AI-draft button gate + `degraded_context` banner + `solicitation.service.ts::draftSection` payload extension | P1.5 | P1.7 |
| P1.7 | `cj/m1-p1-e2e-smoke` | End-to-end smoke: CLI script that POSTs `/draft-solicitation/section` against real Bedrock + atlas-local + asserts `outcome="draft_returned"` + `citations` non-empty + audit row written | P1.4 + P1.6 | — |

P1.1, P1.2, P1.3, P1.5 can all run in parallel after Phase 0. P1.4 + P1.6 require their respective upstream branches. P1.7 is the closing PR.

## 7. Task checklist

### P1.1 — Preflight

- [x] `app/api/preflight.py` with `PreflightResult` Pydantic + `preflight_single_section` + `preflight_batch` (batch fn lives here even though /batch lands in Phase 3 — keeps the policy collocated).
- [x] `tests/api/test_preflight.py`:
  - [x] section_id=C without naics → 422 with `missing_required=["naics", ...]`.
  - [x] section_id=L without naics → 200 with `degraded_context=["naics"]`.
  - [x] All hard-required present → ready=True.
  - [x] Tenant ID missing → 422.

### P1.2 — Programmatic tools

- [x] `app/agents/tools/__init__.py` exports the 4 tools.
- [x] `app/agents/tools/retrieve_far.py` — wraps M2 `build_far_retriever` + `rerank_only` (new thin function split from `rerank_and_gate` per spec §8.1.1).
- [x] `app/agents/tools/retrieve_related.py` — null-arg short-circuit returns empty list with zero Mongo cost.
- [x] `app/agents/tools/gate.py` — uses `config.GATE_*_THRESHOLD` via `gate_thresholds()` helper.
- [x] `app/agents/tools/validate.py` — thin wrapper around `app/citations.py::verify_citations`.
- [x] Per-tool unit tests; gate threshold boundary tests.
- [x] Tenant-isolation regression: `tests/test_retrieval_tenant_isolation.py` extended with a `req_rag_3` test that asserts the tool can't bypass `build_far_retriever`'s tenant pre-filter.

### P1.3 — LLM tools

- [x] `app/agents/tools/extract_requirements.py` with retry logic per spec §8.3.
- [x] `app/agents/tools/draft.py` — single-section variant (takes `section_id: str`); multi-section variant deferred to Phase 3.
- [x] Stubbed-LLM unit tests using `unittest.mock` against `langchain_aws.ChatBedrockConverse`.

### P1.4 — Builder + handler

- [x] `app/agents/prompts.py::SECTION_DRAFTING_SYSTEM_PROMPT`.
- [x] `app/agents/middleware/hitl_gate.py` — module exists; predicate written; **for Phase 1 the predicate's return is always False** (no interrupts fire). Phase 2 lights it up.
- [x] `app/agents/builder.py::build_section_drafter_agent()`.
- [x] `app/api/draft.py` rewrite per spec §4.1 + §19.3 (preflight → guardrails → agent → audit).
- [x] `app/audit.py::_build_record` extended to accept optional `tool_calls: list[ToolCallRecord]`.
- [x] `app/api/draft.py` integration tests with stubbed Bedrock; assert `outcome="draft_returned"` + citations + audit row.

### P1.5 — Frontend Step 1 reactive forms

- [x] `frontend/src/app/components/solicitation-wizard/solicitation-wizard.component.ts` migrates Step 1 from `[(ngModel)]` to `FormGroup` per spec §19.7.
- [x] Add `Validators.required` to 5 fields: title, agencyId, naics, setAside, contractType.
- [x] Next button at line 304 gets `[disabled]="!step1Form.valid"`.
- [x] `solicitation-wizard.component.spec.ts` — step1Form.valid=false → Next disabled.

### P1.6 — Frontend section-card + service

- [x] `section-card.component.ts` gains `@Input() step1Ready: boolean`.
- [x] AI-draft button at line 71 gets `[disabled]="drafting || !step1Ready"`.
- [x] `solicitation.service.ts::draftSection` body extended with `naics`, `set_aside`, `contract_type`, `agency_supplement` from the wizard's Step 1 form state.
- [x] `section-card` renders inline warn banner when `lastResponse.degraded_context.length > 0`.
- [x] Parent wizard passes `[step1Ready]="isStep1ContextReady()"` on every section-card.
- [x] `section-card.component.spec.ts` — `step1Ready=false` → button disabled with tooltip; `step1Ready=true` → enabled.

### P1.7 — End-to-end smoke

- [x] Smoke script `services/ai-orchestrator/scripts/m1_p1_smoke.sh` that runs the curl from spec §16 (single-section happy path) and asserts the response shape with `jq`.
- [x] Document the script in `m2-grounded-retrieval/handoff.md` (or new `m1-handoff.md`) so the next session can run it.

## 8. In-progress checklist (crash recovery)

1. `git log cj/m1-p1-* --oneline` — what's landed.
2. Open §7 above — find first unchecked box.
3. Open the relevant PR branch — confirm rebase against `cj/m2-integration` head.
4. Check tracker §2 active-phase block for the "Next" sentence from the last session.

## 9. Phase 1 exit gate

See tracker §4 Phase 1. All boxes checked.

## 10. Handoff notes

**2026-06-11 (Phase 1 complete on `cj/m1-langchain-integration`):**

- All P1.1–P1.7 tasks landed in one branch (no per-PR branches — single-session implementation).
- Local dev env upgraded to langchain 1.3.7 (was 0.3.7); `langgraph-checkpoint-mongodb` installed.
- Handler keeps a credential-free stub path (`_stub_run`) per CLAUDE.md D-060 — retrieval+rerank+gate run real, generation stubbed.
- HITL middleware structurally present; `HITL_INTERRUPTS_ENABLED=False` until Phase 2 (predicate logic final).
- Frontend: karma test target + tsconfig.spec.json added (repo had no test target); 9 specs green via `npx ng test --watch=false --browsers=ChromeHeadless`. Bundle 482.5 kB (+~11 kB over M2 baseline; ReactiveFormsModule).
- Exit-gate items needing real Bedrock + seeded corpus (LangSmith trace, live `outcome="draft_returned"`) are runnable via `services/ai-orchestrator/scripts/m1_p1_smoke.sh` — NOT yet executed against live stack in this session.
- M2 test file `test_draft_section_endpoint.py` rewritten to M1 contract (hitl_pending removed per design ref §14.1).
