# ADR 0013 — Multi-agent extension: DraftingCoordinatorAgent (Router) + ConsistencyCriticAgent (Subagent)

Date: 2026-06-10
Status: Proposed
Decision-makers: FDE pair (delivery lead + author)
Phase: 1 — AI Adoption · Milestone M1 (LLM-assisted solicitation drafting) extending toward M3 (Agentic source-selection workflow)
Related: ADR-0012 (single-agent draft-solicitation baseline — this ADR layers on top, does not replace) · ADR-0003/0004 (pilot drafting) · ADR-0007 D3 (gate thresholds) · ADR-0008 (tenant + audit + HITL) · ADR-0011 (security attack surface) · PRD §6 REQ-AID-1..4 · LangChain v1.0 multi-agent docs (https://docs.langchain.com/oss/python/langchain/multi-agent)

## Context

ADR-0012 designed `POST /draft-solicitation/section` as a single `create_agent` run — one section per call, one drafter per request. That covers the wizard's per-section "AI-draft" button (UI-driven serial). It does **not** cover:

- A "Draft all AI sections" batch action (drafts C, H, L, M in parallel).
- A cross-section consistency check that validates FAR 15.204-5 L↔M alignment, set-aside ↔ Section K reps, and CLIN coverage Section B ↔ C ↔ F ↔ L — none of which a single-section drafter can see.
- The structural questions the user surfaced after ADR-0012 landed: when to aggregate, when to run a critic pass, whether a coordinator is needed, and the per-section / per-Part / per-claim granularity tradeoff.

LangChain v1.0 (https://docs.langchain.com/oss/python/langchain/multi-agent) documents five multi-agent patterns: **Subagents**, **Handoffs**, **Skills**, **Router**, **Custom Workflow**. None of them ship as a one-line factory (the v1.0 docs explicitly do **not** expose a `create_router` / `create_supervisor` helper as of the 2026-06-10 fetch); each is composition guidance over `create_agent` + `langgraph.types.Send` + `langgraph.StateGraph`.

This ADR is **additive** to ADR-0012. The single-section endpoint and the `SectionDrafterAgent` shape stay exactly as ADR-0012 specifies; this ADR adds (a) a coordinator that fans out to N drafter subagents, (b) a critic agent that runs once post-aggregate, and (c) two new endpoints. Backward compatibility with ADR-0012 is a load-bearing constraint, not a nice-to-have — the cohort's M1 implementation work targets ADR-0012's surface and must not be re-flowed by this ADR.

## Decisions

### D1 — `DraftingCoordinatorAgent` is a custom `StateGraph` with its own `MongoDBSaver` checkpointer, using the v1.0 Router pattern with `langgraph.types.Send`

**Checkpoint the parent graph.** The coordinator's `StateGraph` is compiled with a `MongoDBSaver` (same singleton instance as ADR-0012 D4 — reuses `agent_checkpoints` + `agent_checkpoint_writes` collections). Coordinator `thread_id` = `{solicitation_id}:batch:{request_id}`. Without this, an inner-drafter interrupt propagates `GraphInterrupt` up to the coordinator with no place to land — the coordinator either crashes or has to catch the interrupt in every node body. The standard v1.0 pattern is: parent and child share state through the same checkpointer; `Command(resume=...)` directed at the parent's `thread_id` forwards to the right inner subagent automatically.



**Pattern.** Per https://docs.langchain.com/oss/python/langchain/multi-agent/router, the Router pattern in v1.0 is: a routing step classifies input and dispatches to specialist agents, optionally in parallel; results are synthesized. v1.0 ships no `create_router` helper; the implementation is a custom `langgraph.StateGraph` with `Send` instances returned from the routing node:

```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

class CoordinatorState(TypedDict):
    solicitation_id: str
    tenant_id: str
    request_id: str
    sections_to_draft: list[str]              # filled by plan_drafting_order
    section_results: Annotated[list[FinalDraftSection], operator.add]   # reducer = list-append
    consistency_report: ConsistencyReport | None

def plan_drafting_order(state: CoordinatorState) -> list[Send]:
    # Deterministic routing — no LLM classification.
    # Per D2, only sections that are AI-draftable AND not yet owned by the CO get fanned out.
    return [
        Send("draft_one_section", {
            "section_id": sid,
            "solicitation_id": state["solicitation_id"],
            "tenant_id": state["tenant_id"],
            "request_id": state["request_id"],
        })
        for sid in state["sections_to_draft"]
    ]
```

The node `draft_one_section` is a thin wrapper that invokes `SectionDrafterAgent` (ADR-0012's `create_agent`) and returns its `FinalDraftSection`. The graph's reducer (`Annotated[list[...], operator.add]`) collects fan-in returns into `state["section_results"]`. A subsequent `aggregate` node short-circuits on any interrupted section (D3); a `critic` node runs `ConsistencyCriticAgent` (D4); a terminal node assembles the response.

**Why custom `StateGraph`, not `create_agent`.** `create_agent` is a tool-loop harness; it does not give us a routing-then-fan-out shape with deterministic dispatch. The v1.0 Router page is explicit about this: *"implementations use StateGraph directly with Command/Send primitives."*

**Why NOT the Subagents pattern (where each drafter is a `@tool` wrapping `subagent.invoke`).** Subagents pattern executes sequentially by default per https://docs.langchain.com/oss/python/langchain/multi-agent/subagents — *"the main agent waits for each subagent to complete before continuing."* Parallelism requires "explicit async implementation using a job system" (three-tool start/check/get pattern). For 4 sections that's overkill; `Send` is the documented v1.0 mechanism for the parallelism we need.

**Why NOT the Handoffs pattern.** Per https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs, Handoffs are agent-to-agent control transfer with state persistence across turns — right pattern for chatbot ensembles, wrong pattern for a deterministic fan-out + critic flow. The HTML topology card explicitly flags `Handoffs` as **NOT used** to keep this off the table during review.

**Why NOT one big `create_agent` with all sections as one prompt.** Cost (one massive Sonnet call vs. four parallel ones with separate context budgets), latency (~30s sequential vs. ~6–10s wall-clock), and UX (interrupt-and-resume becomes per-solicitation, blunting the M1 multi-day-pause property ADR-0012 D4 just established).

### D2 — Routing is deterministic, NOT LLM-classified

**Rule** (in `plan_drafting_order`, no LLM call):

```python
AI_DRAFTABLE = {"C", "H", "L", "M"}       # per wizard's AI-draft surfaces

def sections_to_draft(provenances: dict[str, str | None]) -> list[str]:
    """Spawn a drafter for every AI-draftable section with provenance == null.
    Sections already owned by the CO (human / ai / ai-edited) are skipped —
    the CO has taken authorship and the batch path does not overwrite that."""
    return [s for s in sorted(AI_DRAFTABLE) if provenances.get(s) is None]
```

`provenances` comes from the request body (wizard reads its per-section `SectionAudit.provenance` and sends the map). The coordinator does not LLM-classify which sections are "important enough to draft"; the wizard's authoritative section-ownership state is the rule.

**Why deterministic.** Per https://docs.langchain.com/oss/python/langchain/multi-agent/router, LLM classification is recommended when "explicit LLM-based routing classification" is needed — i.e., when input is ambiguous and a model must decide. Our routing input is `{"C","H","L","M"} × provenance_map`; both are structured. LLM-classifying a deterministic mapping is a token-spend with no quality upside and a non-determinism downside (audit replay must be stable).

**Why per-section, not per-Part.** FAR UCF Parts mix drafted/retrieved/human inconsistently — Part I has 2 drafted (C, H) of 8 sections; Part IV has 2 drafted (L, M) of 3; Parts II + III are entirely non-drafted in M1 scope. A per-Part agent either skips most of its Part or wraps human-typed sections in agent shells with nothing to do. The HTML §6 granularity matrix lists this option explicitly with the same rationale. Per-AI-section is the clean fan-out unit.

**Why not per-claim.** ADR-0012's `claim_chunk_map` + `validate_citations` already give per-claim traceability inside one section draft. A per-claim agent would multiply Sonnet calls by ~10× and is exactly the kind of over-decomposition PRD §10 cost-cap discipline argues against.

### D3 — Aggregation policy: short-circuit on any interrupted drafter; report ALL pending interrupts in one response

**Pattern.**

```python
def aggregate(state: CoordinatorState) -> dict:
    interrupted = [r for r in state["section_results"] if r.outcome == "interrupted"]
    if interrupted:
        return {
            "bundle": SolicitationDraftBundle(
                solicitation_id=state["solicitation_id"],
                sections=state["section_results"],
                overall_outcome="batch_interrupted",
            ),
            "skip_critic": True,        # critic does not run when any section paused
        }
    return {"bundle": SolicitationDraftBundle(...), "skip_critic": False}
```

**Why short-circuit on ANY interrupt.** Running the critic over a partial bundle would produce false-positive L↔M misalignment warnings (one of the two sections might not exist yet). Wizard's batch UI renders one "Pending CO decision" panel per interrupted section so the CO can resolve all at once.

**Why not abort the other drafters.** They've already run in parallel — by the time the coordinator's aggregate node executes, all four results are in. No tokens are saved by aborting the non-interrupted runs; their drafts are kept in the bundle (with `outcome="draft_returned"`) and become CO-editable as usual after the interrupts resolve.

**Why not run critic over the partial bundle anyway.** Could be done with severity-clamping (`partial=True → max severity warn`), but adds a Phase 1 special case for a sub-1% scenario. Defer until measured need.

### D4 — `ConsistencyCriticAgent` is a separate `create_agent` invocation, runs once post-aggregate (batch path) AND on demand from wizard Step 12

**Pattern.** A second `create_agent` instance with three tools (one LLM, two programmatic) and a `response_format=ConsistencyReport`. Invoked from two surfaces:

1. **Batch path**: coordinator's `critic` node calls `consistency_critic_agent.invoke(...)` after aggregate succeeds (D3). One agent invocation per batch.
2. **Step 12 review path**: wizard's "Review" step POSTs `/draft-solicitation/critic` with the current sections bundle. Same agent, different entry point.

The critic does NOT chain off the drafters' message history — it receives the assembled bundle as input and treats each section text as its own message. Cross-section critique is a fresh-context task; mixing in drafter token history would dilute it.

**Three tools, three checks:**

| Tool | Type | Model | Validates |
|---|---|---|---|
| `check_l_m_alignment` | LLM | `config.BEDROCK_CRITIC_MODEL` (default Nova Lite; spec-knob) | FAR 15.204-5 — every L instruction maps to an M factor and vice versa. Semantic; not regex-able. |
| `check_set_aside_consistency` | programmatic | — | Section A set-aside (8(a), SDVOSB, WOSB, HUBZone, total small business) matches the FAR clauses required in Section K. Lookup table. |
| `check_clin_coverage` | programmatic | — | Every CLIN in Section B has a SOW reference (C), a delivery schedule (F), and an offeror-pricing instruction (L). Token-match + regex. |

**Why one LLM check and two programmatic.** Set-aside ↔ Section K is a finite FAR-clause lookup; LLM here would be theater. CLIN coverage is a structural cross-reference; same. Only the L↔M alignment requires semantic understanding ("does this M evaluation factor evaluate what this L instruction asks the offeror to submit?") — that's the one place an LLM earns its cost.

**Why one critic, not three.** Three agents would multiply the harness overhead (audit rows, checkpoint state, RunnableConfig) for no parallelism gain — the three checks have no inter-dependency but their total wall-clock is dominated by the one LLM call. One agent invoking three tools is the right granularity.

**Why not chain critic into the drafters.** Same-thread iterative critique (drafter → critic → refine → critic → ...) is the "reflection loop" pattern; it improves quality on hard tasks but multiplies cost and latency. Phase 1's M1 scope is "drafted sections grounded by retrieval"; cross-section refinement is an M3 or Phase 1.5 problem. ADR-0012's `validate_citations` is already a single-pass critic at the intra-section level — the cross-section critic mirrors that single-pass shape at the bundle level.

### D5 — Critic is **non-iterative single-pass, warn-only in Phase 1**

**Rule.** The critic emits a `ConsistencyReport` with severities `info | warn | fail` per check and an `overall_severity`. The bundle's submit gate (Step 13 publish modal — FAR 5.705) **does not consult `overall_severity` in Phase 1**. Wizard renders the warnings inline at Step 12 and the CO chooses whether to act on them; the existing FAR-5.705 CO-approval modal is the only hard gate before publish.

**Why warn-only.** Three reasons.

- **Authority over accuracy** (PRD §7). A critic agent's `fail` severity is model judgment; the CO's approval is statutory authority. Letting a critic block a CO's submit inverts that hierarchy.
- **Limited eval baseline.** ADR-0009 + the eval gate spec measure retrieval quality, not cross-section coherence. We don't have a baseline that says "critic flags 95% of real misalignments at this prompt"; shipping a hard-fail before we know the precision is irresponsible.
- **Migration headroom.** Phase 1.5 / M3 add the hard-fail surface once eval data justifies it. Phase 1 ships the critic with the surface area in place (`ConsistencyReport.blocks_submit: bool` field) but always returns `False` in the agent body. The Phase 1.5 ADR flips the default; no schema migration.

**No iterative reflection loop.** A critic-says-warn does NOT trigger a "fix it" round-trip to the drafters. The CO edits the affected sections (or accepts the warning) and re-submits. Iterative reflection is documented as the v1.0 "Self-Reflection" pattern guidance under Custom Workflow; we explicitly do not use it in Phase 1.

### D6 — New endpoints + Pydantic models, additive to ADR-0012's surface

#### D6.1 New endpoint: `POST /draft-solicitation/batch`

**Body**:

```python
class BatchDraftRequest(BaseModel):
    solicitation_id: str = Field(min_length=1, max_length=128)
    naics: str | None = None
    set_aside: str | None = None
    user_constraints_by_section: dict[Literal["C","H","L","M"], str] = Field(default_factory=dict)
    provenances: dict[Literal["A","B","C","D","E","F","G","H","J","K","L","M"], str | None] = Field(default_factory=dict)
```

**Response**: `SolicitationDraftBundle`:

```python
class SolicitationDraftBundle(BaseModel):
    solicitation_id: str
    sections: list[FinalDraftSection]                # one per drafted section
    overall_outcome: Literal["batch_completed", "batch_interrupted"]
    consistency_report: ConsistencyReport | None    # populated iff overall_outcome == "batch_completed"
    pending_interrupts: list[PendingToolCall] = []  # populated iff overall_outcome == "batch_interrupted"
    request_id: str
    batch_run_id: str                                # = f"{solicitation_id}:batch:{request_id}"
```

**Resume semantics.** A batch run that interrupts is resumed via a NEW endpoint `POST /draft-solicitation/batch/resume`, NOT by re-POSTing `/batch`. The coordinator's `MongoDBSaver` checkpoint (D1) holds the partial state — already-drafted sections, pending interrupts, the original `request_id` and `batch_run_id`. The resume payload carries one decision per pending interrupt:

```python
class BatchResumeRequest(BaseModel):
    batch_run_id: str
    decisions: list[BatchPerSectionDecision]    # one per pending interrupt

class BatchPerSectionDecision(BaseModel):
    section_id: Literal["C","H","L","M"]
    decision: Literal["approve","edit","reject"]
    edited_args: dict | None = None
    reason: str | None = None
```

The handler reads the coordinator checkpoint, builds the matching `Command(resume={"decisions": [...]})` per the v1.0 interrupt protocol, and resumes the parent graph. Interrupted child runs continue from their own checkpoints; non-interrupted children's drafts are preserved in state (no re-drafting, no re-spend); the `batch_run_id` is unchanged across the resume; the critic runs once over the now-complete bundle if all decisions approve/edit.

**Why a `/batch/resume` endpoint despite the earlier "per-section resume composability" framing.** Composing per-section resumes requires passing the just-resumed section text back into a follow-up `/batch` call, which the original `BatchDraftRequest` schema doesn't support — adding the field would conflate "fresh batch" and "continue batch" semantics on one endpoint. A dedicated `/batch/resume` is the simpler design once the coordinator graph is checkpointed (D1); without checkpointing, neither approach works cleanly. The coordinator-checkpoint decision in D1 changes the cost-benefit and unblocks this design.

#### D6.2 New endpoint: `POST /draft-solicitation/critic`

**Body**:

```python
class CriticRequest(BaseModel):
    solicitation_id: str = Field(min_length=1, max_length=128)
    sections: dict[Literal["A","B","C","D","E","F","G","H","J","K","L","M"], str | None]
    set_aside: str | None = None
```

**Response**: `ConsistencyReport` (D4 schema). Standalone — does not require any prior agent run.

#### D6.3 New schemas (`app/agents/schemas.py` additions)

In addition to the existing ADR-0012 schemas:

```python
class LMMismatch(BaseModel):
    type: Literal["l_without_m", "m_without_l", "weak_mapping"]
    l_instruction: str | None
    m_factor: str | None
    severity: Literal["info", "warn", "fail"]
    rationale: str

class LMAlignmentReport(BaseModel):
    mismatches: list[LMMismatch]
    overall_severity: Literal["info", "warn", "fail"]
    model: str
    input_tokens: int
    output_tokens: int

class SetAsideMismatch(BaseModel):
    set_aside: str
    expected_reps: list[str]
    actual_reps: list[str]
    missing: list[str]
    extra: list[str]
    severity: Literal["info", "warn", "fail"]

class SetAsideConsistencyReport(BaseModel):
    mismatches: list[SetAsideMismatch]
    overall_severity: Literal["info", "warn", "fail"]

class CLINGap(BaseModel):
    clin_id: str
    missing_in: list[Literal["C", "F", "L"]]
    severity: Literal["info", "warn", "fail"]

class CLINCoverageReport(BaseModel):
    gaps: list[CLINGap]
    overall_severity: Literal["info", "warn", "fail"]

class ConsistencyReport(BaseModel):
    solicitation_id: str
    run_id: str
    lm_alignment: LMAlignmentReport
    set_aside_consistency: SetAsideConsistencyReport
    clin_coverage: CLINCoverageReport
    overall_severity: Literal["info", "warn", "fail"]
    blocks_submit: bool = False               # Phase 1 = always False
    model_used: str | None = None
    timestamp: datetime
```

### D7 — Backward compatibility with ADR-0012

**The single-section endpoint is untouched.** `POST /draft-solicitation/section` keeps its M1 contract from ADR-0012 D8 verbatim. `SectionDrafterAgent` is invoked the same way; HITL interrupt + resume + abandon endpoints behave identically. The wizard's per-section "AI-draft" button continues to call the single-section endpoint with no coordinator involvement.

**The 13-PR M1 rollout plan (`m1-agentic-draft-workflow.md` §15) stands.** This ADR's implementation lands as a **separate rollout** (§18 in the spec extension) after the ADR-0012 rollout completes — A1..F1 finish first, then the multi-agent extension PRs land on top. The dependency direction is one-way: ADR-0013 requires ADR-0012's SectionDrafterAgent + schemas in place; ADR-0012 does not require any of ADR-0013.

**No schema breakage.** `FinalDraftSection` keeps its 4-value outcome enum from ADR-0012 D3. `SolicitationDraftBundle` and `ConsistencyReport` are NEW additive schemas. Existing audit readers and the wizard's section-card render do not change behavior for single-section runs.

### D7.1 — Rate-limit handling for the batch fan-out

The coordinator's `Send` invocations call `build_section_drafter_agent().invoke(...)` in-process — they do NOT re-enter the FastAPI router, so they do NOT count individually against the per-tenant slowapi limiter (ADR-0011 D4: 30/min, 1000/day). Without compensating control, a single `/batch` HTTP hit costs 4× the Sonnet spend of a single `/section` hit at the same rate-limit cost.

**Two compensating controls:**

1. **Hard cap on fan-out.** `config.MAX_BATCH_FAN_OUT` (default `4` — the count of AI-draftable sections). The coordinator's `plan_drafting_order` raises `ValueError` if `len(sections_to_draft) > MAX_BATCH_FAN_OUT`; handler returns 422 `batch_fan_out_exceeded`. Phase 1 has no scenario producing >4 (the AI-draftable set is fixed), but the cap is a defense-in-depth knob that survives Phase 1.5 additions like new AI-draftable sections.
2. **Multi-cost rate-limit.** The `/batch` handler calls `limiter.hit(N)` (slowapi multi-cost API) where N is the number of sections about to be drafted. A batch of 4 sections costs 4 against the per-minute budget; a batch of 2 (because two sections are already CO-owned) costs 2. The audit row records the multi-cost (`batch.rate_limit_cost = N`).

A malicious caller cannot now amortize per-tenant spend across fewer rate-limit hits than the section count. The single-section endpoint is unchanged (cost 1 per call).

### D8 — Audit + LangSmith span hierarchy for the multi-agent run

**Audit rows (Mongo `audit_log` collection — ADR-0008 D3 shape preserved).**

| Action | When | row.run_id | Joins to |
|---|---|---|---|
| `retrieval_and_generate` | One per `SectionDrafterAgent.invoke` inside a batch | `{sol_id}:{section_id}:{request_id}` | shared `batch_run_id` via the metadata field |
| `agent_resume` | Per per-section resume (single-section endpoint only) | section's `run_id` | same |
| `batch_coordinator_run` | One per batch invocation | `{sol_id}:batch:{request_id}` | parent of all the per-section rows for this batch |
| `batch_resume` | Per `/batch/resume` invocation | same `batch_run_id` as the original batch (preserved across resume per D6.1) | shares `batch_run_id` with the original `batch_coordinator_run` row |
| `consistency_critic` | One per critic invocation (batch or Step 12 standalone) | `{sol_id}:critic:{request_id}` | optional parent join via `batch_run_id` when invoked from a batch |

The `batch_coordinator_run` and `consistency_critic` rows are NEW; they extend the existing schema with the additive `tool_calls[]` sub-record from ADR-0012 D9. Schema-version field (`schema_version`) stays at 1; the new actions are within the existing enum.

**LangSmith span hierarchy (auto-traced when `LANGSMITH_TRACING=true`).**

```
batch_coordinator_run                       (parent span; name="batch_coordinator")
  ├── draft_one_section(C)                  (child span; name="section_drafter")
  │   ├── retrieve_far_clauses               (tool span)
  │   ├── extract_section_requirements        (LLM span)
  │   ├── compute_gate_decision               (tool span)
  │   ├── draft_section_text                  (LLM span)
  │   └── validate_citations                  (tool span)
  ├── draft_one_section(H)                  (parallel sibling)
  ├── draft_one_section(L)                  (parallel sibling)
  ├── draft_one_section(M)                  (parallel sibling)
  ├── aggregate                              (programmatic span; no LLM)
  └── consistency_critic                     (child span; name="consistency_critic")
      ├── check_l_m_alignment                 (LLM span)
      ├── check_set_aside_consistency          (tool span)
      └── check_clin_coverage                  (tool span)
```

`Send`-spawned subagent runs are auto-parented to the calling node's span by LangSmith — no manual span-wrapping needed.

### D9 — Granularity decision (formal closure)

**Decision: per-section default + optional batch via Coordinator. NOT by FAR Parts. NOT per-claim. NOT one-agent-per-solicitation.** Closes the granularity question posed in the user's 2026-06-10 follow-up.

Rejected options + rationale (recap of D2 / HTML §6):

- **Per-Part agents** — Parts mix drafted/human/retrieved inconsistently; no clean fan-out unit. Per-Part agents would be 70%+ empty by section count or wrap human sections in agent shells with nothing to do.
- **Per-claim agents** — multiplies Sonnet calls ~10× per section without a quality upside; `claim_chunk_map` + `validate_citations` already give per-claim traceability.
- **One-agent-per-solicitation** — long wall-clock (~30s), CO can't preview one section at a time, and interrupt-and-resume becomes per-solicitation, blunting the ADR-0012 D4 multi-day-pause UX.

## Consequences

**Closes user follow-up questions.** When to aggregate (D3), critic Y/N + when (D4 + D5), coordinator Y/N (D1), granularity (D9). All four answered.

**Two new endpoints + four new Pydantic models** (`BatchDraftRequest`, `SolicitationDraftBundle`, `CriticRequest`, `ConsistencyReport` and its three sub-reports). Net-additive.

**One new agent + one new coordinator graph.** `ConsistencyCriticAgent` is a `create_agent` instance; `DraftingCoordinatorAgent` is a `langgraph.StateGraph` — different harness shapes for different roles.

**No new env vars are strictly required.** A new optional `BEDROCK_CRITIC_MODEL` (default `amazon.nova-lite-v1:0`) is added to `.env.example`. All other config knobs from ADR-0012 are reused.

**Cost envelope per batch run** ≈ $0.22 USD (4× parallel drafters at ~$0.05 each + 1 critic LLM call at ~$0.015 + programmatic critic checks free). Wall clock dominated by the slowest drafter (~6–10s with Sonnet), not 4× sequential.

**LangSmith trace hierarchy** is auto-parented through `Send` — no manual span wrapping needed (D8).

**Carves out for Phase 2 / M3.** Iterative reflection loops (drafter → critic → refine); critic hard-fail surface (`blocks_submit=True`); per-claim agents; agent-to-agent handoffs; LLM-classified routing if some downstream use case requires it.

**Watchwords this ADR deliberately does NOT smuggle in** (per `feedback_solo_adr_critic_pass.md`): no app-side OpenTelemetry / AIOps rollout (LangSmith is in-agent only, same scope discipline as ADR-0012 D7); no scheduled human-review time budget; no critic hard-fail in Phase 1 (D5); no LLM-classified routing (D2); no per-Part agents that smuggle real-FedRAMP-Parts compliance work into M1 (D2); no managed Bedrock Agents (PRD §4 — Coordinator is hand-built per the multi-agent-must-be-hand-built constraint).

**Explicit non-decisions (deferred to subsequent specs / Phase 1.5).**

- Critic precision baseline — Phase 1.5 measures via eval gate before flipping `blocks_submit` default.
- Section J attachment validation as a fourth critic tool — out of scope until ADR-0012's Section J storage open item is closed.
- LLM-classified routing (e.g., "which set of FAR clauses applies to this NAICS / set-aside combo") — out of scope; deterministic routing covers M1.
- Per-tenant critic model override — uses the same global `BEDROCK_CRITIC_MODEL` config knob for all tenants.
