# ADR 0014 — Per-FAR-Part batch fan-out (supersedes ADR-0013 D1 fan-out shape)

Date: 2026-06-10
Status: Proposed
Decision-makers: FDE pair (delivery lead + author)
Phase: 1 — AI Adoption · Milestone M1 (LLM-assisted solicitation drafting)
Related: ADR-0012 (single-agent baseline — UNCHANGED) · ADR-0013 (multi-agent topology — supersedes the fan-out granularity decision only; preserves the checkpointer, rate-limit, audit, and critic-shape decisions) · PRD §6 REQ-AID-1..4 · FAR 15.204-1 / 15.204-2 / 15.204-3 / 15.204-4 / 15.204-5

## Context

ADR-0013 D1/D2/D9 decided per-section fan-out: the coordinator spawns one `SectionDrafterAgent` per AI-draftable section (C, H, L, M) via `langgraph.types.Send`, producing 4 parallel drafter invocations. The user then pointed at the FAR 15.204-1 Uniform Contract Format four-Part structure and asked whether per-Part fan-out is the right shape, and whether every Part actually warrants an LLM call.

I verified each FAR Part's content via direct fetch on 2026-06-10:

- **FAR 15.204-2 (Part I — Schedule, Sections A–H)** — A is the solicitation form (boilerplate), B is CLINs (tabular numeric data), **C is the SOW (narrative)**, D/E/F/G are short administrative sections (packaging, inspection, deliveries, contract administration), **H is special contract requirements (narrative)**. The two narrative sections C + H are AI-draftable; the others are form/tabular/short-admin and are CO-typed in the wizard today.
- **FAR 15.204-3 (Part II — Contract Clauses, Section I)** — *"The contracting officer shall include in this section the clauses required by law or by this regulation and any additional clauses expected to be included in any resulting contract."* The reg is silent on by-reference vs. full-text. In practice, Section I is a list of FAR/DFARS clauses by reference, populated by a deterministic rule based on set-aside, contract type, and agency supplement. No LLM call is required.
- **FAR 15.204-4 (Part III — List of Documents, Section J)** — *"The contracting officer shall list the title, date, and number of pages for each attached document, exhibit, and other attachment."* Section J is an INDEX of attachments, not the attachments themselves. The wizard collects attachment metadata client-side; no backend LLM call is required.
- **FAR 15.204-5 (Part IV — Representations and Instructions, Sections K, L, M)** — K is offeror representations (largely template/boilerplate), L is instructions to offerors (narrative), M is evaluation factors (narrative). **The regulation contains no explicit requirement mandating alignment between Sections L and M** (verbatim from the FAR fetch). L↔M misalignment is a well-documented GAO bid-protest pattern but is operational best practice + case law, not reg text mandate.

This ADR re-shapes the coordinator fan-out granularity in light of those facts. It supersedes ADR-0013 D1's per-section fan-out and D9's granularity decision (which had already considered and rejected per-Part on weaker information). It preserves all of ADR-0013's other decisions verbatim: checkpointer (D1 checkpointer kwarg), aggregation policy (D3), critic agent existence + invocation surfaces (D4), warn-only Phase 1 policy (D5), audit + LangSmith hierarchy (D8 with action name changes), rate-limit multi-cost wiring (D7.1), and backward compatibility with the ADR-0012 single-section endpoint (D7).

## Decisions

### D1 — Fan-out unit is the AI-draftable FAR Part, not the section

**Pattern.** The coordinator spawns one `PartDrafterAgent` per AI-draftable Part that has at least one section with `provenance == null`. In Phase 1, AI-draftable Parts are exactly two: **Part I (drafts C and/or H)** and **Part IV (drafts L and/or M)**. Maximum fan-out per batch drops from **N=4 sections** to **N=2 Parts**.

```python
AI_PART_TO_SECTIONS: dict[str, frozenset[str]] = {
    "I": frozenset({"C", "H"}),
    "IV": frozenset({"L", "M"}),
}


def _plan(state: CoordinatorState) -> dict:
    parts_to_draft: list[tuple[str, list[str]]] = []
    for part, sections in AI_PART_TO_SECTIONS.items():
        still_null = sorted(s for s in sections if state["provenances"].get(s) is None)
        if still_null:
            parts_to_draft.append((part, still_null))
    return {"parts_to_draft": parts_to_draft}


def _fan_out(state: CoordinatorState) -> list[Send]:
    return [
        Send(f"draft_part_{part}", {
            "part": part,
            "sections": sections,
            "solicitation_id": state["solicitation_id"],
            "tenant_id": state["tenant_id"],
            "request_id": state["request_id"],
            "batch_run_id": state["batch_run_id"],
            "naics": state.get("naics"),
            "set_aside": state.get("set_aside"),
            "user_constraints_by_section": {
                s: state["user_constraints_by_section"].get(s) for s in sections
            },
        })
        for part, sections in state["parts_to_draft"]
    ]
```

**Why per-AI-Part beats per-section.**

The cost saving is marginal — output tokens scale with the total text drafted, not with the number of LLM calls; one Sonnet call drafting C+H together emits roughly the same output tokens as two Sonnet calls drafting C and H separately. The shared retrieval context + shared system prompt overhead is the only true saving (~$0.01 per batch, not material on its own).

**The real win is intra-Part coherence.** C SOW and H special requirements drafted in one LLM context can reference each other deliberately and reuse retrieved-FAR context across both. L instructions and M factors drafted together produce inherent alignment instead of needing the critic to detect it after the fact (D5 below).

**Why not full per-Part (Parts II + III as agents too).** Parts II and III have no LLM-warranted work:

- **Part II (Section I — clauses)**: clause selection is a deterministic function of `(set_aside, contract_type, agency_supplement) → required_clauses`. No model judgment is required. A programmatic `resolve_required_clauses` tool replaces what would have been a vacuous agent.
- **Part III (Section J — attachments)**: per FAR 15.204-4, Section J is a list of `(title, date, page_count)` for each attached document. The wizard collects this client-side (file upload + metadata). No backend agent — not even a tool — is needed in Phase 1.

D3 + D4 below cover the no-agent paths for Parts II + III.

**Why not include Parts II and III in the fan-out as no-op agents.** Per `feedback_solo_adr_critic_pass.md`, an agent shape that wraps non-model work is the kind of goldplating that smuggles complexity into the design. Parts II and III stay out of the agent topology entirely.

### D2 — `PartDrafterAgent` and `SectionDrafterAgent` are two thin specializations of the same harness

**Shared.** Both are `create_agent(...)` instances with the same tool list (`retrieve_far_clauses`, `retrieve_related_solicitations`, `extract_section_requirements`, `compute_gate_decision`, `draft_section_text`, `validate_citations`), the same HITL middleware on `compute_gate_decision`, and the same checkpointer (MongoDBSaver). The harness mechanics established by ADR-0012 are reused verbatim.

**Differ.**

- **System prompt.** `SectionDrafterAgent` is single-section ("draft FAR Section {X}"). `PartDrafterAgent` is Part-aware ("draft FAR Part {N} sections {S1, S2}; the sections are entangled, draft them coherently and with cross-references where appropriate").
- **`draft_section_text` tool variant.** When invoked from a Part agent, the tool accepts a list of section_ids and emits one `SectionDraftSkeleton` per section in its return. When invoked from the single-section agent, it accepts one section_id and emits one skeleton. The tool's input arg discriminates which mode applies; no separate tool name.
- **`response_format`.** `SectionDrafterAgent` returns `FinalDraftSection` (one section). `PartDrafterAgent` returns `PartDraftBundle` (which carries a list of `FinalDraftSection`s, one per drafted section). The PartDraftBundle's `pending_tool_calls` field can hold zero or one (one Part agent has one gate-decision tool call; if it interrupts, both sections in that Part wait on the same CO decision — D7).

**Why not subclass.** v1.0 `create_agent` is a factory function returning a compiled `langgraph.Graph`; there is no subclass-able harness class to override. Both agents are built by separate factory functions (`build_section_drafter_agent()` from ADR-0012 / spec §7; `build_part_drafter_agent(part)` new in this ADR) that internally call `create_agent(...)` with different kwargs.

### D3 — Part II clause selection is a programmatic tool, not an agent

**Module: `app/agents/coordinator/part_ii.py`.**

```python
def resolve_part_ii_clauses(
    set_aside: str | None,
    contract_type: str | None,
    agency_supplement: str | None,
) -> PartIIClauseList:
    """Returns the FAR/DFARS clause set Section I must include for this
    solicitation shape. Pure lookup against the existing FAR snapshot index;
    no LLM call. The same lookup powers wizard step 7 (Section I clauses)
    at submit time."""
```

The coordinator's graph calls this as a regular node (not a `Send` target — not an agent). Output is a `PartIIClauseList`:

```python
class PartIIClauseList(BaseModel):
    clauses_by_reference: list[FARClauseReference]   # e.g., FARClauseReference(citation="52.212-4", title="...")
    source: Literal["far_snapshot_index"]
    snapshot_date: date
    resolved_for: dict[str, str | None]              # echoes the inputs for audit
```

Wizard step 7 (currently hardcoded sample list per the M2 handoff) wires onto the same `resolve_part_ii_clauses` function at submit time — coordinator path and wizard path share one source of truth.

**Why no LLM.** Clause-required-by-FAR is a finite rule set. The FAR clause matrix (which clauses apply to which solicitation shapes) is published; the lookup table is in `docs/reference/far/clause_applicability.json` (new asset; per ADR-0014 D6 below). Using an LLM here is theater.

### D4 — Part III attachment metadata is wizard-side; coordinator does not see it

**Pattern.** Wizard collects `(title, date, page_count, filename)` for each attachment via the existing Section J UI placeholder. On batch submit, the wizard sends the attachment metadata list in the `BatchDraftRequest.part_iii_attachments` field for audit echo, but the coordinator does not pass it to any agent or any tool. The wizard renders the Section J list directly from the metadata it already holds.

**Why even pass it in the request.** Pure audit trail — the request payload records what attachments were claimed at draft time, which the audit row picks up. No business logic consumes it.

**Why not delegate to a backend "attachment validator" tool in Phase 1.** Section J says "title, date, number of pages" — those are wizard-collected metadata fields, not validation-warranting content. Backend validation (e.g., PDF readable? page count matches?) is a Phase 1.5 / M3 chore that interacts with the Section J file-persistence open item (per ADR-0012 D6, handoff §5.5).

### D5 — Critic `check_l_m_alignment` is reframed and lowered to a verification step

**The factual correction.** ADR-0013 D4 + spec §18.5 + HTML claimed `check_l_m_alignment` enforces "FAR 15.204-5 alignment." That language is **wrong on the facts**. FAR 15.204-5 (verbatim from the 2026-06-10 fetch): the regulation describes Sections K, L, M independently and **contains no explicit requirement mandating alignment between Sections L and M.** L↔M misalignment is a GAO bid-protest pattern (operational best practice + case law), not a reg text mandate. ADR-0013 D4 stands corrected.

**The role change.** With `PartIVDrafterAgent` drafting L and M together (D2), inherent alignment is built into the drafting step. The critic's role shifts from "catch misalignment the drafter didn't see" to "verify the Part IV drafter actually aligned them."

- **Tool renamed**: `check_l_m_alignment` → `verify_l_m_consistency`.
- **Threshold tightened**: the tool emits warn only on `weak_mapping` (some L instruction has no clear M factor match); the prior `l_without_m` and `m_without_l` cases are now rare-by-construction (the Part IV drafter sees both at draft time) and surface as `fail` severity if they happen — they indicate the Part IV agent failed at its core job.
- **Falls back to LLM check only on the batch path.** When the critic is invoked via `POST /critic` (Step 12 standalone, no batch agent ran), it still does the full L↔M semantic check using the LLM — the CO may have hand-typed L and M independently. Same tool body, different invocation context.

**Wizard messaging.** Step 12 surface text updated: "L and M coherence check (best practice; not a FAR-mandated alignment)." This avoids overclaiming the legal basis when a CO sees the warning.

### D6 — Endpoint contracts: `/batch` shape changes; `/critic` and single-section unchanged

#### D6.1 `POST /draft-solicitation/batch` request body (extended)

```python
class PartIIIAttachmentMeta(BaseModel):
    title: str
    date: date | None = None
    page_count: int | None = Field(default=None, ge=0)
    filename: str | None = None

class BatchDraftRequest(BaseModel):
    solicitation_id: str = Field(min_length=1, max_length=128)
    naics: str | None = None
    set_aside: str | None = None
    contract_type: str | None = None             # NEW per D3 — needed for Part II clause resolution
    agency_supplement: str | None = None         # NEW per D3
    user_constraints_by_section: dict[Literal["C","H","L","M"], str] = Field(default_factory=dict)
    provenances: dict[Literal["A","B","C","D","E","F","G","H","J","K","L","M"], str | None] = Field(default_factory=dict)
    part_iii_attachments: list[PartIIIAttachmentMeta] = Field(default_factory=list)   # NEW per D4 — audit echo only
```

#### D6.2 `POST /draft-solicitation/batch` response body

```python
class SolicitationDraftBundle(BaseModel):
    solicitation_id: str
    parts: dict[Literal["I", "II", "III", "IV"], PartResult]   # CHANGED — keyed by Part now
    overall_outcome: Literal["batch_completed", "batch_interrupted"]
    consistency_report: ConsistencyReport | None
    pending_interrupts: list[PendingToolCall] = []
    request_id: str
    batch_run_id: str


class PartResult(BaseModel):
    part: Literal["I", "II", "III", "IV"]
    kind: Literal["llm_drafted", "programmatic_resolved", "wizard_provided"]
    sections: dict[str, FinalDraftSection | PartIIClauseList | PartIIIAttachmentMeta | None]
```

`PartResult.kind` distinguishes the three production methods (LLM-drafted = Parts I + IV; programmatic = Part II; wizard-provided pass-through = Part III). The `sections` map carries the section-level results: each AI-drafted section has its own `FinalDraftSection` (preserved from ADR-0012's contract), Section I carries a `PartIIClauseList`, Section J carries the per-attachment metadata.

**Why preserve `FinalDraftSection` per section inside a Part result.** The wizard's `section-card` component renders per-section; baking the Part-level grouping into the agent's output but keeping the section-level shape inside lets the wizard rendering stay unchanged. Per-section `run_id`, `gate_decision`, `citations`, `requires_human_review` continue to surface at the wizard's `section-card` level.

#### D6.3 `POST /draft-solicitation/batch/resume` — unchanged structurally, scope changes

The endpoint signature from ADR-0013 D6 stays. The `BatchPerSectionDecision.section_id` literal narrows from `Literal["C","H","L","M"]` to `Literal["C","H","L","M"]` (no change in the enum, but the decision list maps to per-Part interrupts now). One PartDrafter agent has one gate-decision interrupt; if it pauses, the wizard surfaces ONE interrupt for that whole Part. The CO resumes with one decision; resume re-enters the Part agent which then drafts both sections (or one, if only one was null to begin with) per the approved/edited args.

**Why one decision per interrupted Part, not per section.** PartDrafter's HITL middleware fires once on the single `compute_gate_decision` tool call inside that Part's run; there is exactly one pending decision for the Part. The CO sees "Part IV — needs review" not "Section L — needs review; Section M — needs review."

### D7 — HITL blast radius: one Part = one interrupt; CO ergonomic trade-off acknowledged

The per-section ADR-0013 design allowed Section M to pass while Section L paused (or vice versa). The per-Part design entangles them — if `PartIVDrafterAgent.compute_gate_decision` hits the hitl band, both L and M wait on one CO decision.

**Why accept the entanglement.** L and M are entangled by design (D5). Drafting M while L pauses is exactly the "draft inconsistent halves of Part IV" failure mode the per-Part shape eliminates. Forcing one CO decision per Part is the correct surface for an entangled pair of sections.

**Wizard surface impact.** ADR-0013 specced one "Pending CO decision" panel per pending interrupt. With Part-level interrupts, that's at most two panels per batch (one for Part I, one for Part IV) instead of up to four. UI deltas are net-smaller.

### D8 — Backward compatibility with ADR-0012 single-section path is preserved

`POST /draft-solicitation/section` keeps its M1 contract from ADR-0012 D8. `SectionDrafterAgent` remains the per-section harness; HITL interrupt + resume + abandon behave identically. The wizard's per-section "AI-draft" button continues to route to the single-section endpoint with no coordinator involvement.

The new `PartDrafterAgent` does NOT replace `SectionDrafterAgent` — the two co-exist. Single-section path uses the section agent; batch path uses the Part agents. A CO who wants to redraft only Section M (without touching L) uses the single-section endpoint, which spawns one `SectionDrafterAgent("M")` — exactly the M2 / ADR-0012 shape.

### D9 — Audit + LangSmith span hierarchy

Audit row `action` values update:

| Action | When | run_id format |
|---|---|---|
| `retrieval_and_generate` | One per `SectionDrafterAgent.invoke` (single-section path) | `{sol_id}:{section_id}:{request_id}` |
| `agent_resume` | Per single-section resume | section's run_id |
| `batch_coordinator_run` | One per `/batch` invocation | `{sol_id}:batch:{request_id}` |
| `batch_resume` | Per `/batch/resume` invocation | same `batch_run_id` as original batch |
| `part_drafter_run` (NEW, supersedes per-section rows inside a batch) | One per `PartDrafterAgent.invoke` from inside the batch coordinator | `{sol_id}:part_{part}:{request_id}` |
| `consistency_critic` | One per critic invocation | `{sol_id}:critic:{request_id}` |

LangSmith hierarchy:

```
batch_coordinator_run                          (parent span)
  ├── plan                                      (programmatic node span)
  ├── resolve_part_ii_clauses                   (programmatic tool span; no LLM child)
  ├── pass_through_part_iii_attachments         (programmatic node span; no LLM child)
  ├── part_drafter_run(I)                       (parallel sibling)
  │   ├── retrieve_far_clauses
  │   ├── compute_gate_decision
  │   ├── draft_section_text (called with [C, H])
  │   └── validate_citations (called once per section drafted)
  ├── part_drafter_run(IV)                      (parallel sibling)
  │   ├── retrieve_far_clauses
  │   ├── compute_gate_decision
  │   ├── draft_section_text (called with [L, M])
  │   └── validate_citations
  ├── aggregate                                 (programmatic span)
  └── consistency_critic                        (child span)
      ├── verify_l_m_consistency                 (LLM span; renamed per D5)
      ├── check_set_aside_consistency             (tool span)
      └── check_clin_coverage                     (tool span)
```

### D10 — Granularity decision formally updated (supersedes ADR-0013 D9)

Per-AI-Part fan-out for the batch path; per-section for the single-section path. Final.

Rejected (recap, with the corrected reasoning):

- **Per-Part for Parts II + III** — D3 + D4 collapse them to non-agent paths; agent-shape is reserved for LLM-warranted work.
- **Per-section fan-out (ADR-0013 D1's prior shape)** — costs more on input-token overhead (shared retrieval + system prompt × 4 vs. × 2) and forfeits intra-Part coherence between C↔H and L↔M.
- **One agent per whole solicitation** — same reasons as ADR-0013 D9.
- **Per-claim agents** — same reasons as ADR-0013 D9.

## Consequences

**Closes the user's 2026-06-10 follow-up on per-Part granularity.** AI-draftable Parts I + IV become the fan-out unit; Parts II + III are non-agent.

**Net delta from ADR-0013.** Fan-out drops from 4 to 2 parallel drafters. Adds one programmatic tool (`resolve_part_ii_clauses`) and one wizard-side data path (Part III metadata). Renames one critic tool (`check_l_m_alignment` → `verify_l_m_consistency`) and reframes its role from FAR-mandate enforcement to operational coherence verification (D5). Adds two new schemas (`PartIIClauseList`, `PartResult`) and modifies `SolicitationDraftBundle` to be Part-keyed (D6.2).

**Cost.** Per-batch envelope unchanged at ~$0.22 (output tokens dominate; same total text drafted). Input tokens drop ~3000 per batch (~$0.01 saving — not material on its own; the win is coherence, not cost).

**Wizard impact.** Smaller than ADR-0013 estimated: per-Part HITL surfaces a single "Pending CO decision" per Part, not per section. Step 12 critic warning text updated to drop the FAR-15.204-5-mandate claim.

**Carves out for Phase 2 / M3.** L↔M alignment as a hard-fail surface; per-section override inside a per-Part draft (e.g., "redraft only M from this Part IV bundle"); Part II clause-matrix expansion beyond the snapshot; Part III backend file-persistence + validation.

**Watchwords this ADR deliberately does NOT smuggle in** (per `feedback_solo_adr_critic_pass.md`): no app-side OTel rollout, no host-disk-encryption cohort prereq, no scheduled human-review time budget, no LLM-classified routing (D1 remains deterministic), no managed Bedrock products, no Part II / Part III agents-for-the-sake-of-symmetry.

**Explicit non-decisions.**

- Whether Section K (Part IV reps/certs) should be programmatically resolved like Section I (Part II clauses) — out of scope; K stays template-driven + CO-typed per ADR-0012's M2 baseline. Phase 1.5 may revisit.
- Whether D/E/F/G (Part I admin sections) should optionally be LLM-assisted — out of scope; wizard keeps them human-typed.
- Whether `PartDrafterAgent` should self-critique L↔M before emitting (vs. relying on the standalone critic) — out of scope; D5's verification step covers it.
