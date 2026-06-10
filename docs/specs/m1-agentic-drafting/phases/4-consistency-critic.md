# M1 · Phase 4 — Consistency critic (verify_l_m_consistency + set_aside + clin_coverage)

**Type:** vertical slice (UI + API). End state: At wizard Step 12 (Review), critic agent runs over the section bundle; warnings render inline; Step 13 publish modal still gates on FAR 5.705 CO approval (critic never blocks submit — Phase 1 warn-only invariant).

**Status:** see [`m1-agentic-drafting/tracker.md`](../tracker.md) §1.

**Design reference:** [`m1-agentic-drafting/design-reference.md`](../design-reference.md) §18 (critic mechanics), §18.12.2 (`verify_l_m_consistency` rename per ADR-0014 D5).

---

## 1. Goal

Build the cross-section consistency critic agent + its 3 tools + the standalone `/critic` endpoint. Swap the Phase 3 coordinator's critic stub for the real agent. Wizard Step 12 invokes the critic and renders warnings.

## 2. Vertical slice

```
CO completes drafting (single-section path or batch path)
  → advances to Step 12 (Review)
  → wizard POSTs /draft-solicitation/critic with current sections bundle:
    {solicitation_id, set_aside, sections: {A: "...", B: "...", C: "...", ...}}
  → critic agent (create_agent with 3 tools, response_format=ConsistencyReport):
    ├── verify_l_m_consistency (LLM — Nova Lite or Sonnet config knob)
    │   "Section L says offerors must submit a past-performance questionnaire.
    │    Section M lists 'past performance' as factor 3 of 5. ALIGNED."
    │   → LMAlignmentReport(mismatches=[], overall_severity="info")
    ├── check_set_aside_consistency (programmatic)
    │   set_aside=SDVOSB requires FAR 52.219-27 in Section K; not found.
    │   → SetAsideConsistencyReport(mismatches=[{missing: ["52.219-27"]}],
    │                                overall_severity="warn")
    ├── check_clin_coverage (programmatic)
    │   CLIN 0001 referenced in B + C + F + L; CLIN 0002 missing in F.
    │   → CLINCoverageReport(gaps=[{clin_id: "0002", missing_in: ["F"],
    │                                severity: "warn"}],
    │                       overall_severity="warn")
    └── response_format → ConsistencyReport(overall_severity="warn",
                                            blocks_submit=False)
  → wizard renders inline warnings on Step 12:
    ⚠ Set-aside SDVOSB: Section K missing 52.219-27 [Fix Section K →]
    ⚠ CLIN 0002 not referenced in Section F (Delivery) [Fix Section F →]
  → CO either fixes or accepts → clicks "Submit for internal review"
  → Step 13 publish modal fires (FAR 5.705 CO approval; critic warnings
    do NOT gate this — Phase 1 warn-only)
```

## 3. In scope

- `app/agents/critic/builder.py::build_consistency_critic_agent()`.
- `app/agents/critic/prompts.py::CONSISTENCY_CRITIC_SYSTEM_PROMPT`.
- `app/agents/critic/tools/lm_consistency.py::verify_l_m_consistency` (LLM tool — renamed from `check_l_m_alignment` per ADR-0014 D5).
- `app/agents/critic/tools/set_aside.py::check_set_aside_consistency` (programmatic).
- `app/agents/critic/tools/clin_coverage.py::check_clin_coverage` (programmatic — with section_b None guard).
- `POST /draft-solicitation/critic` standalone endpoint.
- Phase 3's coordinator `_critic` node body swapped from stub to real-critic invocation.
- Audit row for `action="consistency_critic"`.
- Wizard Step 12 component renders `ConsistencyReport` inline.
- `solicitation.service.ts::critic()` method.

## 4. Out of scope

- Critic hard-fail surface (`blocks_submit=True`) — Phase 1.5 trigger after precision baseline.
- Iterative reflection loops (Phase 2 / M3).
- Section J attachment validation as a fourth critic tool (Phase 1.5).

## 5. Dependencies

- Phase 0 schemas include all of LMMismatch, LMAlignmentReport, SetAsideMismatch, SetAsideConsistencyReport, CLINGap, CLINCoverageReport, ConsistencyReport, CriticRequest.
- Phase 3 ideally completed (so the coordinator's stubbed critic node can be swapped). If Phase 3 slips, Phase 4 can land the standalone `/critic` endpoint without the swap; Phase 3's exit then includes the swap as a follow-up.

## 6. PR breakdown + parallelism

```
[P0 done; P3 ideally done]
   │
   ├── P4.1 critic tools ──────────────┐
   ├── P4.2 critic builder + prompt ───┤
   │                                   ├─ converge → P4.4 /critic endpoint
   ├── P4.3 frontend Step 12 ──────────┘                  │
   │                                                      │
   └── P4.5 swap coordinator stub (only if P3 done) ───── ├─ → P4.6 e2e
                                                          │
   P4.5 may slip into Phase 3's task list if P3 finishes after P4.4.
```

| PR | Branch | What lands | Parallel-after | Sequential-before |
|---|---|---|---|---|
| P4.1 | `cj/m1-p4-critic-tools` | 3 critic tool modules + per-tool unit tests | P0 | P4.2 |
| P4.2 | `cj/m1-p4-critic-builder` | `app/agents/critic/builder.py` + prompt + integration test (stubbed LLM) | P4.1 | P4.4 |
| P4.3 | `cj/m1-p4-fe-step12` | Wizard Step 12 component renders ConsistencyReport inline + service method | P0 | P4.6 |
| P4.4 | `cj/m1-p4-critic-endpoint` | `app/api/critic.py` + `POST /critic` route + integration test with hand-built bundle | P4.2 | P4.6 |
| P4.5 | `cj/m1-p4-coord-critic-swap` | Phase 3's `_critic` stub in `app/agents/coordinator/nodes.py` swaps to real critic agent invocation | P3 + P4.4 | P4.6 |
| P4.6 | `cj/m1-p4-e2e-critic` | E2E: known-mismatched fixture → /critic returns expected warnings; batch path → critic runs after aggregate | P4.4 + P4.5 + P4.3 | — |

## 7. Task checklist

### P4.1 — Critic tools

- [ ] `app/agents/critic/__init__.py`, `tools/__init__.py`, `tools/{lm_consistency,set_aside,clin_coverage}.py`.
- [ ] `verify_l_m_consistency` — LLM tool body uses `ChatBedrockConverse(config.BEDROCK_CRITIC_MODEL).with_structured_output(LMAlignmentReport)`. Per ADR-0014 D5, role differs by invocation path (batch verify vs standalone full-check); the same tool body handles both — the difference is what L and M text it sees.
- [ ] `check_set_aside_consistency` — programmatic; uses `SET_ASIDE_REQUIRED_CLAUSES` dict from spec §18.5. Honors `config.SET_ASIDE_STRICT_EXTRA` for warn-on-extra behavior.
- [ ] `check_clin_coverage` — programmatic; per ADR-0015 critic-pass minor fix, includes `section_b is None` guard returning info-severity skip (parallel to the other two tools' missing-section handling).
- [ ] Unit tests:
  - L↔M: mocked Sonnet with crafted L+M text → expected `LMAlignmentReport`.
  - Set-aside: table-driven over 5 set-asides × {matched, missing-required, extra}.
  - CLIN: multi-CLIN solicitations × {all-aligned, 1-missing-warn, 2+-missing-fail-but-clamped-to-overall-warn}.

### P4.2 — Critic builder

- [ ] `app/agents/critic/builder.py::build_consistency_critic_agent()` per spec §18.4.
- [ ] `app/agents/critic/prompts.py::CONSISTENCY_CRITIC_SYSTEM_PROMPT` — directs agent to call all 3 tools, never iterate, return a single `ConsistencyReport`.
- [ ] Critic agent: `create_agent(model=Chat..., tools=[3 tools], system_prompt=..., response_format=ConsistencyReport, name="consistency_critic")` — NO middleware, NO checkpointer (warn-only, no interrupt, short runs).
- [ ] Integration test with stubbed tool returns: critic emits a correctly-shaped `ConsistencyReport` with `blocks_submit=False`.

### P4.3 — Frontend Step 12

- [ ] Wizard Step 12 component (likely `solicitation-wizard-step-12.component.ts` or extension of existing wizard) renders three sub-reports:
  - LMAlignmentReport: list of mismatches with severity-colored badges.
  - SetAsideConsistencyReport: missing-clauses + extras lists.
  - CLINCoverageReport: gap rows with "Fix Section X →" deep-links to the relevant section card.
- [ ] `solicitation.service.ts::critic(bundle)` POSTs `/critic` and returns `ConsistencyReport`.
- [ ] Step 12 auto-invokes critic on entry; loading state while pending.

### P4.4 — /critic endpoint

- [ ] `app/api/critic.py` with `POST /draft-solicitation/critic` per spec §18.2 + ADR-0014 D6.2.
- [ ] Reads `CriticRequest` body; builds critic agent; invokes; writes audit row `action="consistency_critic"`.
- [ ] Standalone path (NOT batch-coordinator-driven): the "full LLM semantic check" mode per ADR-0014 D5 — L and M may be hand-typed, so the LLM check is the only alignment surface.
- [ ] Mount route in `app/main.py`.
- [ ] Integration tests covering 3 fixture solicitations: clean, set-aside-mismatch, CLIN-gap.

### P4.5 — Coordinator critic swap (requires P3 complete)

- [ ] `app/agents/coordinator/nodes.py::_critic` body swaps from stub to `build_consistency_critic_agent().invoke(...)`.
- [ ] Integration test against the coordinator path: known-good bundle → critic emits low-severity report; known-mismatch bundle → warn-severity report.
- [ ] LangSmith trace inspection: critic span fires AFTER aggregate span (parent-child ordering).

### P4.6 — E2E critic

- [ ] CLI smoke script in `services/ai-orchestrator/scripts/m1_p4_critic_smoke.sh` running the curl from spec §18.10 (critic standalone).
- [ ] Add a `m1_p4_batch_critic_smoke.sh` that runs /batch end-to-end with critic-driven warnings (depends on P4.5).

## 8. In-progress checklist

1. `git log cj/m1-p4-* --oneline`.
2. §7 first unchecked.
3. If P3 hasn't completed yet, defer P4.5 — land P4.1 + P4.2 + P4.3 + P4.4 first (standalone path works without P3).
4. Tracker §2 "Next" sentence.

## 9. Phase 4 exit gate

See tracker §4 Phase 4.

## 10. Handoff notes

(empty)
