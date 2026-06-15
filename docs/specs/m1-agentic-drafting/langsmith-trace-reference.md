# M1 LangSmith trace reference (P5.3)

What a healthy trace looks like for each M1 endpoint. Tracing is pure env-var
config (ADR-0012 D7): set `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` at
process start; project defaults to `acquire-gov-m1-draft`.

Filters: every run carries `tags=["m1", ...]` and searchable metadata
(`request_id`, `solicitation_id`, `tenant_id`, `batch_run_id` where
applicable). Token counts + per-LLM-span latency are captured automatically —
never duplicated into metadata.

---

## 1. `POST /draft-solicitation/section` — canonical happy path

```
section_drafter                       ← run name (agent name, §7)
├── model (Sonnet)                    ← decides first tool call
├── tool: retrieve_far_clauses        ← Bedrock Rerank child span inside
├── model
├── tool: retrieve_related_solicitations   (only when naics/set_aside set)
├── model
├── tool: extract_section_requirements     (only when constraints non-null;
│                                            Nova Lite LLM child span)
├── model
├── tool: compute_gate_decision       ← input args carry rerank_top_score
├── model
├── tool: draft_section_text          ← THE Sonnet spend (one per run)
├── model
├── tool: validate_citations
└── model → structured output: FinalDraftSection
```

Red flags: `draft_section_text` BEFORE `compute_gate_decision` (tool-order
drift — the eval metric tracks the rate); two `draft_section_text` spans in
one run; a `retrieve_far_clauses` span after drafting.

**Interrupted variant**: the trace ENDS after the model emits the
`compute_gate_decision` tool call — no gate ToolMessage, no draft span. The
resume call appears as a separate run on the same thread metadata
(`run_id = {sol}:{section}:{request_id}` joins them).

## 2. `POST /draft-solicitation/batch` — per-Part fan-out

```
batch_coordinator_run                 ← compiled graph name (§18.12)
├── plan
├── resolve_part_ii                   ← no LLM children (programmatic)
├── pass_through_part_iii             ← no LLM children
├── draft_part_I                      ← Send target
│   └── part_i_drafter                ← child agent run (same tool tree as §1,
│                                        draft_section_text with ["C","H"])
├── draft_part_IV                     ← parallel sibling of draft_part_I
│   └── part_iv_drafter
├── aggregate
└── critic
    └── consistency_critic            ← child agent run (§3 shape)
```

Exit-gate check (tracker §4 P3): `part_i_drafter` + `part_iv_drafter` are
PARALLEL siblings under the coordinator parent — overlapping wall-clock
windows, not sequential. Critic span fires AFTER aggregate (tracker §4 P4).

**Interrupted variant**: the interrupted `draft_part_X` span shows the child
agent ending on the gate tool call; `aggregate`/`critic` are absent. The
`/batch/resume` run re-enters as the same thread (`{sol}:batch:{request_id}`).

## 3. `POST /draft-solicitation/critic` — standalone Step 12

```
consistency_critic
├── model (Nova Lite)
├── tool: verify_l_m_consistency      ← inner Nova Lite LLM child span
├── tool: check_set_aside_consistency ← programmatic, no children
├── tool: check_clin_coverage         ← programmatic, no children
└── model → structured output: ConsistencyReport
```

Red flags: any tool invoked twice (the critic is single-pass — the system
prompt forbids iteration); a fourth tool span; `blocks_submit=true` anywhere
in the output (boundary clamp should make this impossible — file a bug).

---

Verification one-liners live in `phases/5-hardening.md` + the smoke scripts
(`scripts/m1_p1_smoke.sh`, `m1_p3_smoke.sh`, `m1_p4_*_smoke.sh`,
`m1_e2e_smoke.sh`).
