# M1 · Phase 3 — Batch coordinator (per-AI-Part fan-out)

**Type:** vertical slice (UI + API). End state: CO clicks "Draft AI Parts" → backend coordinator fans out to PartIDrafter (C+H) + PartIVDrafter (L+M) in parallel via `Send`; Part II clauses resolved programmatically; Part III metadata passed through; aggregated bundle returned.

**Status:** see [`m1-agentic-drafting/tracker.md`](../tracker.md) §1.

**Design reference:** [`m1-agentic-drafting/design-reference.md`](../design-reference.md) §18.12 (per-AI-Part shape — supersedes §18.1–§18.10 on fan-out).

---

## 1. Goal

Build the multi-agent topology per ADR-0014. After this phase, the wizard can batch-draft all 4 AI-draftable sections in two parallel LLM calls instead of four sequential single-section calls.

## 2. Vertical slice

```
CO completes Step 1 + 2 + 3 (form fields)
  → Step 4 (Section C) — instead of per-section AI-draft, clicks a NEW
    "Draft AI Parts" button at top of wizard
  → POST /draft-solicitation/batch
    {solicitation_id, naics, set_aside, contract_type, agency_supplement,
     provenances: {A: "human", B: "human", C: null, D: "human", E: "human",
                   F: "human", G: "human", H: null, J: "human", K: "human",
                   L: null, M: null},
     user_constraints_by_section: {C: "quarterly cadence",
                                   L: "max 25 page proposal"},
     part_iii_attachments: [{title: "Past performance Q",
                              date: "2026-06-10", page_count: 4}]}
  → preflight_batch passes (all hard-required present)
  → coordinator graph:
    ├── plan → sections_to_draft per AI-Part:
    │           Part I → [C, H], Part IV → [L, M]
    ├── resolve_part_ii_clauses (programmatic) → PartIIClauseList
    ├── pass_through_part_iii (programmatic) → PartIIIAttachmentList
    ├── Send(draft_part_I) ─┐
    ├── Send(draft_part_IV)─┤ parallel
    └── aggregate ──────────┘
       → SolicitationDraftBundle.parts {I, II, III, IV}
       → no interrupts → critic node runs (handed off to Phase 4)
  → response 200 with overall_outcome="batch_completed", parts populated
  → wizard renders each PartResult into its section-card; user advances
```

## 3. In scope

- `app/agents/coordinator/graph.py` — custom `StateGraph` with checkpointer.
- `app/agents/coordinator/nodes.py` — `_plan`, `_fan_out_per_part`, `_draft_part_i`, `_draft_part_iv` (catching `GraphInterrupt`), `_resolve_part_ii`, `_pass_through_part_iii`, `_aggregate`, `_route_after_aggregate`, `_critic` (delegates to Phase 4's critic).
- `app/agents/coordinator/part_ii.py` — `resolve_part_ii_clauses` programmatic lookup + `docs/reference/far/clause_applicability.json` asset.
- `app/agents/coordinator/part_iii.py` — wizard-passthrough adapter.
- `app/agents/part_drafter/builder.py::build_part_drafter_agent(part)`.
- `app/agents/part_drafter/prompts.py::PART_DRAFTING_SYSTEM_PROMPTS["I" | "IV"]`.
- `app/agents/tools/draft.py` — multi-section variant (`draft_section_text` accepting `list[section_id]`).
- `app/api/batch.py` — `POST /batch` handler with slowapi multi-cost hit.
- `app/api/batch_resume.py` — `POST /batch/resume` handler.
- Audit rows for `batch_coordinator_run`, `part_drafter_run`, `batch_resume`.
- Frontend "Draft AI Parts" button + per-Part HITL surface.

## 4. Out of scope

- Critic invocation from coordinator: the node EXISTS in P3 but its body delegates to Phase 4's critic agent. P3 lands a "critic_stub" placeholder that returns `ConsistencyReport.overall_severity="info"` with empty sub-reports. Phase 4 swaps the stub for the real critic agent.
- Eval-gate metrics (Phase 5).

## 5. Dependencies

- Phase 2 completed (HITL middleware fires + /resume works + multi-day pause proven).
- Phase 0 schemas include all of PartResult, PartIIClauseList, PartIIIAttachmentMeta, PartDraftBundle, SolicitationDraftBundle, BatchDraftRequest, BatchResumeRequest, FARClauseReference.
- FAR clause applicability matrix: `docs/reference/far/clause_applicability.json` asset must exist. P3 PR P3.4 creates it.

## 6. PR breakdown + parallelism

```
[P2 done]
   │
   ├── P3.1 multi-section draft tool ────┐
   ├── P3.2 PartDrafterAgent builder ────┤
   ├── P3.3 Part II prog tool ───────────┤
   ├── P3.4 clause_applicability.json ───┤ (independent asset; can land any time)
   ├── P3.5 coordinator graph ───────────┘── ─→ P3.6 endpoints + multi-cost ─→ P3.8 e2e
   │                                                                          │
   ├── P3.7 frontend batch button ───────────────────────────────────────────┘
```

| PR | Branch | What lands | Parallel-after | Sequential-before |
|---|---|---|---|---|
| P3.1 | `cj/m1-p3-tool-multi-section` | `draft_section_text` accepts `list[section_id]`; emits dict[section_id, SectionDraftSkeleton]; backward-compat: singleton list works exactly as P1 single-section | P2 | P3.2 + P3.5 |
| P3.2 | `cj/m1-p3-part-drafter` | `app/agents/part_drafter/` package; builder + Part-aware prompts + `PartDraftBundle` response_format | P3.1 | P3.5 |
| P3.3 | `cj/m1-p3-part-ii` | `app/agents/coordinator/part_ii.py::resolve_part_ii_clauses` + lookup table; consumes `clause_applicability.json` | P2 | P3.5 |
| P3.4 | `cj/m1-p3-clause-matrix` | `docs/reference/far/clause_applicability.json` asset listing required clauses keyed on (set_aside, contract_type, agency_supplement) + manifest entry | P2 (independent) | P3.3 |
| P3.5 | `cj/m1-p3-coord-graph` | `app/agents/coordinator/graph.py` + `nodes.py`; critic node stubbed; node-level unit tests | P3.2 + P3.3 | P3.6 |
| P3.6 | `cj/m1-p3-batch-endpoints` | `app/api/batch.py` + `app/api/batch_resume.py`; slowapi multi-cost wiring; audit rows; integration tests | P3.5 | P3.8 |
| P3.7 | `cj/m1-p3-fe-batch` | Wizard "Draft AI Parts" button + per-Part HITL surface + bundle render | P2 (frontend-independent) | P3.8 |
| P3.8 | `cj/m1-p3-e2e-batch` | End-to-end smoke with all 4 sections null + interrupt-on-one-Part test | P3.6 + P3.7 | — |

P3.1, P3.3, P3.4, P3.7 can start in parallel after P2. P3.2 sequences after P3.1; P3.5 needs P3.2 + P3.3; P3.6 needs P3.5; P3.8 is closing.

## 7. Task checklist

### P3.1 — Multi-section draft tool variant

- [ ] `app/agents/tools/draft.py::draft_section_text` accepts `section_ids: list[str]`; backward-compat tests for singleton-list invocation (Phase 1 path still works).
- [ ] Tool emits `dict[str, SectionDraftSkeleton]` keyed by section_id.
- [ ] Prompt: instructs the model to draft sections coherently when given multiple section_ids ("Part I sections C + H share retrieved FAR context — cross-reference where appropriate").
- [ ] Unit test with mocked Sonnet that returns malformed dict → tool surfaces a typed error the handler catches.

### P3.2 — PartDrafterAgent builder

- [ ] `app/agents/part_drafter/__init__.py`, `builder.py`, `prompts.py`.
- [ ] `PART_DRAFTING_SYSTEM_PROMPTS["I"]` + `PART_DRAFTING_SYSTEM_PROMPTS["IV"]` per spec §18.12.2.
- [ ] `build_part_drafter_agent(part)` per spec §18.12.2.
- [ ] Integration test with stubbed tools: invoke a Part I agent against 2 mocked retrieved chunks; assert `PartDraftBundle` carries C + H sections.

### P3.3 — Part II programmatic tool

- [ ] `app/agents/coordinator/part_ii.py::resolve_part_ii_clauses` per spec §18.12.2.
- [ ] Reads from `docs/reference/far/clause_applicability.json` (loaded once at import).
- [ ] Returns empty `PartIIClauseList` (with explicit `resolved_for` audit echo) when args don't match a known combination — not a 500.
- [ ] Unit test: 5 known set-asides × 2 contract types = 10 fixture cases asserting expected clause lists.

### P3.4 — Clause-applicability matrix asset

- [ ] `docs/reference/far/clause_applicability.json` listing required FAR/DFARS clauses by `(set_aside, contract_type, agency_supplement)` triple.
- [ ] Add entry to `docs/reference/far/MANIFEST.sha256` so the FAR snapshot verifier (`.github/scripts/verify-far-snapshot-manifest.sh`) covers it.
- [ ] Documented in `docs/reference/far/MANIFEST.md` with sourcing notes (which FAR sections informed the matrix).

### P3.5 — Coordinator graph + nodes

- [ ] `app/agents/coordinator/__init__.py`, `graph.py`, `nodes.py` per spec §18.12.2.
- [ ] `_draft_part_i` + `_draft_part_iv` invoke `build_part_drafter_agent(part)` and catch `GraphInterrupt` → synthesize a Part-level interrupted bundle (mirror of Phase 2 P2.1 pattern for the section-level case).
- [ ] `_critic` node is a stub returning `ConsistencyReport.overall_severity="info"` with empty sub-reports until Phase 4 lands.
- [ ] Coordinator graph compiled with checkpointer (same `MongoDBSaver` singleton).
- [ ] Unit tests per node + `tests/agents/coordinator/test_graph_compose.py` asserting graph wiring.

### P3.6 — Batch endpoints

- [ ] `app/api/batch.py` per spec §18.12.2 + slowapi multi-cost `limiter._storage.hit(_tenant_key(request), cost=n-1)` per spec §18.6.1.
- [ ] `app/api/batch_resume.py` per spec §4.2 (the spec's `/batch/resume` block).
- [ ] Both routes mounted in `app/main.py`.
- [ ] Audit row writers: `batch_coordinator_run`, `batch_resume`.
- [ ] Integration test in `tests/api/test_batch.py`:
  - 4 sections null → batch_completed.
  - 1 section pre-owned (provenance="human") → coordinator skips it, drafts only 3.
  - Forced hitl-band on one drafter → batch_interrupted; non-interrupted drafts preserved.
  - Resume completes the interrupted Part → batch_completed bundle.

### P3.7 — Frontend batch UI

- [ ] Wizard "Draft AI Parts" button (likely above Step 4 or in a sidebar).
- [ ] `solicitation.service.ts::draftBatch(...)` + `resumeBatch(batchRunId, decisions)`.
- [ ] Section-card per-Part interrupt surface: when a Part fan-out interrupts, both sections in that Part share one "Pending CO decision" panel.
- [ ] Bundle render: each PartResult's sections populate their respective section-cards (C/H/L/M) and Section I gets the resolved clause list from PartResult.II.

### P3.8 — End-to-end batch smoke

- [ ] CLI smoke script `services/ai-orchestrator/scripts/m1_p3_smoke.sh` runs the curl from spec §18.10.
- [ ] Pause-restart test extended: container restart between batch and resume.
- [ ] LangSmith trace inspection: assert parent `batch_coordinator_run` span has `part_i_drafter` + `part_iv_drafter` parallel child spans.

## 8. In-progress checklist

1. `git log cj/m1-p3-* --oneline` — what's landed.
2. §7 — first unchecked box.
3. P3.4 (clause matrix) can be assembled in parallel with everything else — easy unblock candidate.
4. Tracker §2 "Next" sentence.

## 9. Phase 3 exit gate

See tracker §4 Phase 3.

## 10. Handoff notes

(empty)
