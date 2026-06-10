# ADR 0012 — Agentic draft-solicitation workflow: tool decomposition, structured outputs, HITL persistence, LangSmith tracing

Date: 2026-06-10
Status: Proposed
Decision-makers: FDE pair (delivery lead + author)
Phase: 1 — AI Adoption · Milestone M1 (LLM-assisted solicitation drafting) extending toward M3 (Agentic source-selection workflow)
Related: ADR-0003 (pilot drafting endpoint) · ADR-0004 (pilot review/remediation) · ADR-0008 (tenant isolation, audit, HITL) · ADR-0011 (security attack surface) · PRD §6 REQ-AID-1..4 · PRD §11 open questions — "Gate implementation primitives + how a paused run is persisted across a multi-day human delay" and "Drafting UX: synchronous vs. streaming delivery" · LangChain v1.0 OSS docs (URLs cited per decision)

## Context

M2 shipped a single-pass synchronous `POST /draft-solicitation/section` (`services/ai-orchestrator/app/api/draft.py:187-438`). One handler does retrieval → rerank → one `ChatBedrockConverse` call → citation hard-fail → audit. There is no agent, no per-step tool decomposition, no checkpointer, no Human-In-The-Loop middleware. The handoff doc (`docs/specs/m2-handoff.md` §3) explicitly lists `LangGraph create_agent`, `HumanInTheLoopMiddleware`, and `MongoDBSaver` as stubbed.

The PRD describes M1 drafting in capability terms (REQ-AID-1..4), not in workflow-step terms. PRD §11 leaves the gate primitive + paused-run persistence + sync-vs-streaming UX deliberately open for an ADR to close. PRD §4 forbids managed Bedrock products (Agents, Guardrails) — agentic orchestration must be hand-built. PRD §4 also rules out "AIOps / OpenTelemetry rollout, circuit breakers, resilience engineering" — this ADR's observability scope is therefore deliberately narrow: per-run trace into LangSmith (the LangChain-native tool), not a full app-side OTel rollout.

The wizard UI already encodes most of the decisions a workflow has to honor. `frontend/src/app/components/solicitation-wizard/solicitation-wizard.component.ts:1-520` enumerates 13 UCF steps; `section-card.component.ts:1-416` is the AI shell that calls `/draft-solicitation/section` and renders provenance, gate badges, confidence dots, and citations; `solicitation.service.ts:58-79` is the one method that posts to the orchestrator. Only **four** wizard steps (4 — Section C / SOW, 6 — Section H / Special Requirements, 10 — Section L / Instructions, 11 — Section M / Evaluation Factors) are AI-drafted; Section I is retrieved-only; Sections A/B/D/E/F/G/J/K are human-typed. The agentic redesign is therefore scoped to one endpoint, invoked four times per solicitation in the worst case.

This ADR settles **what the agentic shape of that endpoint is**, **which steps stay programmatic vs. go to an LLM**, **what Pydantic shape flows between steps**, **when retrieval fires inside the run**, **how a paused run survives a multi-day CO delay**, and **what the UI/contract impact is**.

## Decisions

### D1 — One agent per section invocation, harness = `langchain.agents.create_agent`

**Pattern.** Each call to `POST /draft-solicitation/section` constructs one agent via `langchain.agents.create_agent` (v1.0 OSS — https://docs.langchain.com/oss/python/langchain/agents) and invokes it once. The agent's tool list, system prompt, response schema, middleware, and checkpointer are fixed at construction; the agent loop chooses which tools to call and in what order, subject to the tool list and the response schema. There is no LangGraph `StateGraph` hand-rolled — `create_agent` is the harness.

**Signature** (only kwargs we pass):

```python
from langchain.agents import create_agent
from langchain_aws import ChatBedrockConverse

agent = create_agent(
    model=ChatBedrockConverse(model=config.BEDROCK_GEN_MODEL),
    tools=[
        retrieve_far_clauses,          # programmatic
        retrieve_related_solicitations, # programmatic (intra-tenant)
        extract_section_requirements,  # LLM (Nova Lite)
        draft_section_text,            # LLM (Sonnet — the only Sonnet call per run)
        validate_citations,            # programmatic
        compute_gate_decision,         # programmatic
    ],
    system_prompt=SECTION_DRAFTING_SYSTEM_PROMPT,
    response_format=FinalDraftSection,  # Pydantic — see D3
    middleware=[hitl_middleware],       # see D6
    checkpointer=mongodb_saver,         # see D4
    name="section_drafter",             # surfaces as the run name in LangSmith
)
```

**Rationale.** The v1.0 docs root (https://docs.langchain.com/oss/python/langchain/overview) is explicit: *"Agent = Model + Harness. LangChain provides `create_agent`: a minimal, highly configurable harness."* `create_agent` is the only first-class agent constructor in v1.0; the pre-v1.0 patterns (`LLMChain`, `PromptTemplate.from_template() | llm`, `RunnableLambda` chains) are absent from every v1.0 example we want to emulate. We avoid them per the known-hallucination note in the originating ask.

**Why not LangGraph `StateGraph` hand-rolled.** `create_agent` returns a compiled graph internally and exposes the same `.invoke` / `.stream` surface. Hand-rolling buys us per-node observability that LangSmith already provides for free on `create_agent` runs (D7). The escalation lever — switch to `StateGraph` — exists if we ever need a non-tool-loop control flow (e.g., explicit fan-out across sections in M3). Phase 1 does not.

**Why not one big LLM call (status quo).** M2 today is exactly that: one `ChatBedrockConverse` call inside `services/ai-orchestrator/app/api/draft.py` with the retrieved chunks delimiter-wrapped into the prompt. The cohort's M3 work needs the tool-decomposed shape (statutorily-reserved tools must be visible to the HITL middleware), and the cost split below (D2) is unreachable from a single-call shape because every step pays Sonnet rates.

### D2 — Programmatic-vs-LLM tool split: keep LLMs out of every step that doesn't need generation

**Programmatic tools** (no model call; deterministic; cheap):

| Tool | What it does | Why programmatic |
|---|---|---|
| `retrieve_far_clauses(section_id, query, k=20)` | Wraps the existing `build_far_retriever` factory (`retrieval.py:76-112`) + `MongoDBAtlasHybridSearchRetriever.invoke` + `rerank_and_gate`. Returns `RetrievedEvidence`. | Already proven; classifier is rule-based; rerank is a Bedrock Rerank 1.0 call (not an LLM completion). |
| `retrieve_related_solicitations(naics, set_aside, tenant_id, k=5)` | Same retriever factory, filtered to `doc_class=internal_solicitation` + same `tenant_id`. Returns `RelatedSolicitations`. | Intra-tenant lookup; tenant pre-filter (ADR-0008 D2) enforces REQ-RAG-3. |
| `validate_citations(draft_text, retrieved_ids)` | Existing `citations.verify_citations` (`citations.py:32-61`). Returns `ValidationResult` with `unknown_chunk_ids[]`. | String matching; no model needed. |
| `compute_gate_decision(rerank_top_score, mode)` | Existing rerank-and-gate threshold logic (`rerank.py:100-146`). Returns `pass` / `hitl` / `withhold` / `rerank_unavailable_passthrough`. | Pure threshold arithmetic per ADR-0007 D3. |

**LLM tools** (model call; expensive; only where generation is required):

| Tool | Model | Why this model |
|---|---|---|
| `extract_section_requirements(user_constraints, section_id)` | A lightweight Bedrock model — initial choice `amazon.nova-lite-v1:0`, finalized in the spec | Short, structured extraction from free-form CO input. Bedrock pricing as of 2026-Q2 puts Nova Lite at $0.06/M input + $0.24/M output vs. Sonnet's $3.00/M + $15.00/M — roughly a 50× input / 60× output cost-per-token gap. Not user-visible text. |
| `draft_section_text(section_id, evidence, requirements, related_solicitations)` | `BEDROCK_GEN_MODEL` (currently `us.anthropic.claude-sonnet-4-5-v1:0`) | This is the only step whose output reaches the CO unchanged. Cost optimization is not acceptable here; per PRD §7 "grounded or withheld" applies, and ADR-0011 D1.2 mandates `ChatBedrockConverse` with delimiter-wrapped context for prompt-injection resistance. |

**No LLM judge in the per-run loop.** `app/guardrails.py::_nova_micro_classifier` is still stubbed (`m2-handoff.md` §5.3) and lives at the request edge, not inside the agent loop. Phase 1.5 wires it; this ADR does not depend on it.

**Cost envelope per section draft (target).** One Sonnet call for `draft_section_text` (~6k input tokens after delimiter-wrap, ~2k output) plus one Nova Lite call for `extract_section_requirements` (~500 in / 200 out, skipped when `user_constraints` is null) plus one Bedrock Rerank 1.0 call (`retrieve_far_clauses`; a second rerank for `retrieve_related_solicitations` is left out — D2 sub-decision below). Programmatic tools are free. Estimated **~$0.05 per section draft** at current pricing — well inside the M1 cost-attribution guidance in PRD §6 REQ-AID-3.

**The cost envelope is a target, not a measured floor.** Two operational caveats:
- The `withhold` short-circuit (D6) only fires when the gate-aware middleware (see D6 fix) interrupts *before* `draft_section_text` runs. Under the v1.0 `create_agent` harness, tool-call ordering is set by the LLM's reasoning step — not by the harness. The system prompt + tool docstrings constrain it; they do not enforce it. If a misbehaving model run drafts before checking the gate, no token spend is saved on that run. The eval gate (ADR-0009) will catch sustained mis-ordering; per-run cost variance is accepted.
- `extract_section_requirements` model choice is **left as a spec-level config knob** (`config.BEDROCK_EXTRACT_MODEL` default `amazon.nova-lite-v1:0`). Cost-class chip in the visualization is "low" regardless of the specific lightweight model chosen.

**Rationale for the split.** PRD §7 "authority over accuracy" forbids letting model confidence downgrade a hard gate; programmatic `compute_gate_decision` makes the gate authority structurally LLM-independent. PRD §7 "auditable by default" means every transition needs a recorded reason; programmatic tools have deterministic, hashable outputs that the audit row (D9) can quote verbatim instead of summarizing.

### D3 — One Pydantic model per stage; the response schema is the agent's structured output

**Pattern.** Every tool's input is a Pydantic `BaseModel` with explicit `Field(description=...)` (mandatory for `@tool` per https://docs.langchain.com/oss/python/langchain/tools — *"Type hints are required as they define the tool's input schema"*). Every tool's output is also a Pydantic `BaseModel` so downstream tools can typecheck what they receive. The agent's final output is enforced via `response_format=FinalDraftSection` on `create_agent`, which lands the result in `state["structured_response"]` (https://docs.langchain.com/oss/python/langchain/structured-output — *"Pass a Pydantic BaseModel directly; result lands in state['structured_response']"*). We do **not** call `with_structured_output` on the chat model — that is the v1.0 "outside of agents" idiom; we are inside an agent.

**Schemas (names + structural shape only; the spec owns full `Field(...)` definitions and validation constraints):**

- `SectionPlanContext` — section + solicitation identity, tenant, optional `naics`/`set_aside`/`user_constraints`, `request_id`, derived `run_id`. The `section_id` enum is **the M2 `_FAR_SECTION_ENUM` exactly — `{A,B,C,D,E,F,G,H,J,K,L,M}`, no I.** The wizard's Section I (clauses) is retrieved-only and remains served by the existing `POST /retrieve` endpoint, not by `/draft-solicitation/section` (see D5.1 below); this preserves the M2 contract and avoids a parallel "agent that doesn't draft" branch.
- `RetrievedEvidence` — list of retrieved `Chunk` rows + classifier weights + `rerank_top_score`. **`gate_decision` is NOT a field of this model** — it is produced by a separate tool (D2 `compute_gate_decision`) so that the HITL middleware (D6) has a tool to gate on whose *input args* fully determine its return value.
- `RelatedSolicitations` — list of `SolicitationSummary` + count. Intra-tenant only.
- `ExtractedRequirements` — list of `Requirement` rows + source-text hash + model + token counts. Parsed by the lightweight extractor model; on malformed structured output the tool retries once and on second failure returns `requirements=[]` (treated by the agent as "no extracted constraints, use raw `user_constraints` as supplemental hint"). Spec owns retry policy.
- `SectionDraftSkeleton` — `section_text` + `claim_chunk_map: list[ClaimCitation]`. The map carries `chunk_id` per claim so `validate_citations` is mechanical.
- `ValidationResult` — `valid: bool`, `unknown_chunk_ids: list[str]`, `grounding_score: float`.
- `GateDecisionResult` — produced by the `compute_gate_decision` tool. Fields: `gate_decision: Literal["pass","hitl","withhold","rerank_unavailable_passthrough"]`, `rerank_top_score: float | None`, `reason: str`. The tool's *input* takes `rerank_top_score` directly so middleware can decide to interrupt by reading the input args (D6).
- `FinalDraftSection` — **this is the agent's `response_format`**. Canonical outcome enum, **used by D9 audit row and HTML stage 7 alike**:
  ```
  outcome: Literal[
      "draft_returned",
      "withheld",
      "interrupted",
      "citation_verification_failed",
  ]
  ```
  Plus: `section_text: str | None`, `section_id: str` (matches `_FAR_SECTION_ENUM`), `citations: list[Citation]`, `gate_decision: ...`, `requires_human_review: bool`, `rerank_top_score: float | None`, `request_id: str`, `run_id: str`. The M2 outcome `"hitl_pending"` is **removed** by this ADR — the agentic flow's hitl path is the `"interrupted"` outcome plus the new `/resume` endpoint (D8), not the M2 "draft now, CO checks a box later" pattern. The M2 `"query_blocked"` outcome is **not** a `FinalDraftSection.outcome` because it is raised by the handler before the agent runs (403 short-circuit, audit-only). UI migration is the additive new surface in `section-card.component.ts` for the `"interrupted"` outcome (D8).

**Why structured output everywhere.** M2's `draft.py` returns a raw `(text, citations[], tokens)` tuple parsed by hand. That coupling pushes JSON-parsing fragility into the handler. Pydantic on the wire (in *and* out of every tool) means parse failures raise at the boundary with a typed error the audit row can pin, not inside business logic.

**Why `response_format` on the harness instead of `with_structured_output` on the chat model.** The v1.0 docs position `with_structured_output` as the *outside-of-agents* path. Once we are using `create_agent`, the idiomatic structured-output path is `response_format` on the harness, which routes via `ProviderStrategy` (native — Anthropic on Bedrock) or `ToolStrategy` per https://docs.langchain.com/oss/python/langchain/structured-output. Mixing both inside one run risks the model deciding the response is "really" the structured-output tool call and short-circuiting the actual tool loop.

### D4 — Thread-id lifecycle + `MongoDBSaver` checkpointer for multi-day HITL pauses

**Thread identity.** One agent run = one `thread_id` = `{solicitation_id}:{section_id}:{request_id}`. Concatenating all three guarantees:
- one solicitation has at most one in-flight run per UCF section at a time,
- a re-draft of the same section (user clicked "AI-draft Section C" twice) gets a fresh `request_id` and therefore a fresh thread — the old paused thread is preserved for audit replay,
- the audit row's existing `request_id` field (`audit.py:87-134`) joins naturally to the checkpoint table on `thread_id` startswith `solicitation_id:section_id:`.

**Checkpointer.** `MongoDBSaver` from the `langchain-mongodb` integration package (import path: `from langgraph.checkpoint.mongodb import MongoDBSaver`). Reference: https://langchain-mongodb.readthedocs.io/en/latest/langgraph_checkpoint_mongodb/saver/langgraph.checkpoint.mongodb.saver.MongoDBSaver.html. The saver is not listed on `docs.langchain.com/oss/python/langgraph/persistence` — it lives in the integration package; the spec pins the exact constructor kwargs (Mongo client, db name, checkpoint + writes collection names).

**Why TTL=None.** PRD §11 names "paused run survives a multi-day human delay" as the open question. A multi-day TTL is too brittle (CO out for a week breaks the pause); zero TTL keeps the run pausable indefinitely. **Retention is not promised to match the audit row's 6-year floor in this ADR** — checkpoint state is operational, not compliance-of-record (the audit row is). D8.2 above covers the orphan-thread sweeper; long-tail retention beyond the sweeper window is a Phase 1.5 / M3 decision, not pre-empted here.

**What MongoDB stores.** Every step writes a full state snapshot keyed by `(thread_id, checkpoint_ns, checkpoint_id)`. Full message history is persisted, not summarized. Reviewer-side resume reads the latest checkpoint and continues; no summary loss.

**Why not the existing `audit_log` collection.** Audit is append-only structured rows for OIG replay (ADR-0008 D3). Checkpoints are full agent state for in-system resume. Different shapes, different access patterns, different retention controls. Co-locating them muddies both.

**Why not in-memory (`MemorySaver`).** Multi-day pause requires persistence across uvicorn restarts. `MemorySaver` is the LangGraph default for tests; not viable here.

### D5 — Retrieval timing: agent decides via `retrieve_*` tool calls; tenant filter is structural, not negotiable

**D5.1 — Section I bypass.** Section I (FAR clauses) is **retrieved-only** in the wizard and **continues to be served by `POST /retrieve`**, not by the new agentic `/draft-solicitation/section` endpoint. Reasoning: Section I needs no drafting (M2 today renders a hardcoded sample list, future work resolves via `/retrieve` at submit time per the wizard's existing handling). Keeping it out of the agent endpoint preserves the M2 `_FAR_SECTION_ENUM` (D3) and avoids a degenerate "agent that doesn't draft anything" code branch.

**Pattern.** Retrieval is **not** a fixed first step in the handler — it is a tool the agent chooses to call. The agent's system prompt instructs it to call `retrieve_far_clauses` before any drafting; the response-format validator additionally requires `citations: list[Citation]` non-empty when `outcome == "draft_returned"`. The structured-output strategy makes "draft returned without citations" a Pydantic validation failure, not a stylistic concern. As noted in D2's cost caveats, tool ordering is steered by the system prompt + tool docstrings, not enforced by the harness; the cost-saving short-circuit on `withhold` depends on the model honoring that steering, and the eval gate (ADR-0009) is what catches sustained drift.

**Why the agent chooses, not the handler.**
- An agentic shape lets M3 reuse the same tool surface for source-selection drafting where the relevant evidence set is *different per section* (e.g., FAR Part 15 for SSA, prior CPARs for past-performance). Hardcoding "always retrieve first" in the handler would force a re-write.
- It lets the agent call `retrieve_related_solicitations` opportunistically (only when `naics`/`set_aside` are known) — a fixed pipeline would either always pay that cost or hard-code skip logic.

**Tenant isolation stays structural.** `retrieve_far_clauses` and `retrieve_related_solicitations` both call `build_far_retriever(tenant_id=...)` internally; the factory enforces the kw-only `tenant_id` per ADR-0008 D2. The agent **cannot** call a retriever without a tenant pre-filter — the tool function reads `tenant_id` from `RunnableConfig` (passed at `agent.invoke` time, see D7), not from a tool argument. The agent has no way to pass a different tenant in; the locked-passing `pytest -m req_rag_3` gate (ADR-0008 D2) still proves isolation end-to-end.

**Why not pre-fetch then pass to the agent.** That was the M2 shape (`draft.py:238` builds retriever; `draft.py:258-294` calls rerank+gate; both run before any LLM step). It works but conflates the retrieval policy with the handler. Tool-as-policy localizes the decision and is testable in isolation.

### D6 — `HumanInTheLoopMiddleware` interrupts on `compute_gate_decision` via input-args predicate (not return value)

**The mechanism point.** `HumanInTheLoopMiddleware` per LangChain v1.0 (https://docs.langchain.com/oss/python/langchain/middleware) decides to interrupt by inspecting the `ToolCall` object — specifically `tool_call.name` and `tool_call.args`. **`tool_call.args` carries the tool's input arguments, not its return value.** The harness has not executed the tool yet when the predicate runs; that is the point of pre-tool interruption.

This shapes the gate tool's signature. `compute_gate_decision` is defined to take `rerank_top_score: float` as a tool argument (sourced by the agent from the prior `retrieve_far_clauses` ToolMessage in state). The tool body is a pure threshold function that returns `GateDecisionResult` (D3); the middleware predicate runs the *same* threshold against the input arg to decide whether to interrupt:

```python
# tool — pure, deterministic from input
@tool
def compute_gate_decision(rerank_top_score: float | None) -> GateDecisionResult:
    """Decide pass/hitl/withhold from a rerank top-score per ADR-0007 D3."""
    # threshold constants resolved from app.config
    ...

# middleware — same thresholds, applied to the input arg
hitl_middleware = HumanInTheLoopMiddleware(
    interrupt_on={"compute_gate_decision": _interrupt_on_hitl_range},
)

def _interrupt_on_hitl_range(tool_call) -> bool:
    score = tool_call.args.get("rerank_top_score")
    if score is None:
        # rerank_unavailable_passthrough — degraded mode; do NOT interrupt
        return False
    return config.GATE_WITHHOLD_THRESHOLD <= score < config.GATE_PASS_THRESHOLD
```

**Why the predicate is input-only.** A "non-pass" decision is fully determined by the score the agent passes in. Moving the threshold into both the tool and the predicate looks like duplication, but it is the cost of using the documented v1.0 interrupt mechanism without inventing a custom post-tool middleware. The spec wraps both behind a single `gate_thresholds()` helper so they cannot drift; one source-of-truth, two read sites.

**Fire rule.** Middleware interrupts only when `score ∈ [withhold_threshold, pass_threshold)` — the `hitl` band. The other non-pass states are handled without interrupt:
- `withhold` (score < withhold_threshold) — no interrupt; the agent reads the tool's return, the response-format validator + system prompt direct the agent to terminate without calling `draft_section_text`. Outcome `"withheld"`. No Sonnet spend (assuming the agent honors the steering — see D2 caveat).
- `rerank_unavailable_passthrough` (score == None) — no interrupt; agent proceeds with degraded draft + warning. M2 status quo. Outcome `"draft_returned"` with `requires_human_review=True`.

**Why interrupt on `hitl` only.** `hitl` is the case where the gate is uncertain and a CO preview-and-decide saves both the Sonnet spend *and* gives the CO an editable handle on the run (resume `Command` accepts an `edit` decision that can adjust the constraints before the draft tool runs). For `withhold`, there is no editable handle that would make a draft useful; for `rerank_unavailable_passthrough`, blocking on Bedrock outages would compound the incident.

**Why not interrupt on `validate_citations` or `draft_section_text`.** Citation failure is a hard error (raise → 422 — same shape as M2). Interrupting after `draft_section_text` has already executed wastes the token spend it was meant to save.

**Why not a custom post-tool middleware that reads the tool's return value.** Theoretically cleaner ("interrupt iff *return* is hitl"), but requires either a custom `AgentMiddleware` subclass with an `after_tool` hook — public API surface for which the v1.0 docs do not yet cite a stable example — or wrapping the tool by hand. Standing on the documented `HumanInTheLoopMiddleware` is the lower-risk path; the input-args-driven mechanism above is functionally equivalent and uses only the surface the docs warrant.

**Resume protocol.** On interrupt, the handler returns `outcome="interrupted"` + the `run_id` and the pending tool-call payload. The CO resumes via the new `/resume` endpoint (D8) carrying `Command(resume={"decisions": [{"type": "approve" | "edit" | "reject", ...}]})` per https://docs.langchain.com/oss/python/langgraph/interrupts. Per the interrupt protocol, `approve` lets the gate-decision tool execute as if the score were in the `pass` band; `edit` lets the CO adjust the `rerank_top_score` argument (or set a flag the gate tool consumes); `reject` causes the agent to terminate with outcome `"withheld"`.

**Multi-day pause is unchanged from D4.** The middleware uses the checkpointer; no separate persistence path.

### D7 — LangSmith tracing via env vars; per-invoke metadata via `RunnableConfig`; no app-side OTel rollout

**Wiring.** Three env vars enable LangSmith auto-tracing for every `create_agent` invocation (https://docs.langchain.com/langsmith/observability):

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...                  # repo-root .env, never committed
LANGSMITH_PROJECT=acquire-gov-m1-draft
```

When set, `agent.invoke` automatically emits a hierarchical trace with one span per LLM call, one span per tool call, and a parent span for the full run. No code change required beyond setting env vars and constructing the agent normally.

**Per-invoke metadata.** At `.invoke` time:

```python
agent.invoke(
    {"messages": [{"role":"user","content": user_prompt}]},
    config={
        "configurable": {
            "thread_id": f"{solicitation_id}:{section_id}:{request_id}",
            "tenant_id": tenant_id,            # consumed by retrieve_* tools per D5
            "co_user_id": co_user_id,
        },
        "tags": ["m1", "draft-solicitation", f"section-{section_id}"],
        "metadata": {
            "request_id": request_id,
            "solicitation_id": solicitation_id,
            "section_id": section_id,
            "tenant_id": tenant_id,
        },
    },
)
```

`tags` + `metadata` show up as filter facets in LangSmith. We do **not** add Bedrock token counts to metadata — LangSmith auto-captures per-LLM-span token + latency, and duplicating them in metadata is noise.

**Scope discipline.** This is **not** an OpenTelemetry rollout. PRD §4 explicitly excludes "AIOps / OpenTelemetry rollout, circuit breakers, resilience engineering." LangSmith is the LangChain-native observability tool that *only* traces what runs inside `create_agent`; it does not instrument the FastAPI middleware, the rate limiter, the Mongo driver, or the rest of the request path. We are wiring the per-LLM-run trace, not a platform observability stack. If the cohort needs end-to-end request tracing, that is Phase 2.

**Outage behavior.** If `LANGSMITH_TRACING=true` is set but LangSmith is unreachable, the LangChain client buffers spans and discards on overflow; `agent.invoke` does **not** block on trace flush. Operational story: a LangSmith outage degrades the developer-facing trace UI but does not impact a draft request. The spec confirms by smoke-running the agent with `LANGSMITH_API_KEY` deliberately set to an invalid value.

**Redaction is a Phase-1.5 trigger, not a Phase-1 decision.** As long as PRD §10's synthetic-data-only constraint holds, full input/output trace capture is acceptable and useful. When seed corpus expands to anything beyond the FAR public-domain snapshot, the spec adds the documented LangSmith input/output redaction env vars.

### D8 — UI adjustment: moderate (additive contract + one new surface); existing wizard rendering survives intact

**What stays.** The wizard component tree, the 13-step structure, the provenance FSM in `section-card.component.ts`, the soft-gate badge surface, the confidence dots, the citation-list expand UI in `citation-list.component.ts`, and the Step 13 hard-gate publish modal (FAR 5.705). None of these need a substantive change.

**What changes.**

1. **Endpoint response shape — additive.** `DraftSectionResponse` gains `run_id: string` (the LangGraph `thread_id`). Outcome enum gains `"interrupted"` and **drops** `"hitl_pending"` (per D3 — `interrupted` + the new resume flow replace it). The M2 hitl-soft-gate "draft now, CO checks a box later" pattern is no longer reachable from this endpoint.
2. **New endpoint: `POST /draft-solicitation/section/resume`.** Body: `{ run_id, decision: "approve" | "edit" | "reject", edited_args?: ..., reason?: string }`. Response: same `DraftSectionResponse` shape. Per D6, a resume runs the agent forward from the gate checkpoint; the resumed run will only interrupt again if the gate tool is re-invoked (which only happens if the agent loop re-decides to re-retrieve — uncommon by construction).
3. **D8.1 — Resume authorization model.** The `/resume` endpoint requires the same `X-Tenant-ID` header as the original draft call. The resumer's user_id and role are captured into the audit row (`actor.user_id`, `actor.role`) per ADR-0008 D3 — same shape as the original-draft audit. Phase 1 does not bind resume authority to "the CO of record on this thread"; any user with the CO role and matching `X-Tenant-ID` can resume. Per-thread CO-of-record binding is a Phase 1.5 / M3 follow-up (see ADR-0008 D2 + handoff §5.4: audit-log-reader role exists; a parallel "agent-thread-resumer" role is the same shape).
4. **D8.2 — Concurrent re-draft + orphan-thread policy.** Re-drafting the same section spawns a fresh `request_id` and therefore a fresh `thread_id` per D4. The prior paused thread becomes an orphan (no UI surface holds its `run_id`) but is preserved in `agent_checkpoints` for audit replay. The spec adds a `POST /draft-solicitation/section/abandon` endpoint (caller-asserted, optional) and a background sweeper that marks orphan threads `abandoned` after 30 days of no resume traffic. Sweeper retention is **not** the audit-row retention (which stays at the FAR-4.805-analog 6-year floor inherited from ADR-0008 D3); only the live checkpoint state is reclaimed.
5. **New UI surface in `section-card.component.ts`.** When `lastResponse.outcome === "interrupted"`, render a "Pending CO decision" panel with three buttons (Approve, Edit constraints, Reject) that POST to `/resume`. The `run_id` is persisted in the per-section `SectionAudit` block alongside the existing `aiRequestId` so a refreshed wizard can recover the pending interrupt.

**Adjustment magnitude (qualitative; spec owns the day-estimates).** Frontend: additive — one new endpoint client method, one new render surface, one new audit-block field. Backend: substantive — `draft.py` handler body re-shapes around `create_agent`, a new `/resume` handler lands, six tool modules plus the gate-aware middleware plus the checkpointer wiring. Pydantic models: net-additive — existing models keep their shape; new intermediate models per D3.

**Why not a streaming/SSE UX.** PRD §11 names "sync vs streaming delivery" as the open question. We close it for Phase 1 as **synchronous with interrupt-and-resume**. Streaming would add an EventSource layer to the Angular wizard and a streaming-response surface to FastAPI — both are nontrivial and neither is required to satisfy "paused run survives multi-day delay" (D4 already does that). If Phase 1.5 cohort feedback wants progressive draft rendering, the agent's `.stream()` mode is the upgrade path and does not change any of D1–D7.

### D9 — Audit shape: one row per agent run (unchanged contract) + per-tool sub-records, same collection

**Pattern.** The existing `audit_log` collection (ADR-0008 D3) keeps its current row shape. The agentic run writes **one terminal row** with `outcome` drawn from `FinalDraftSection.outcome` (D3 canonical enum: `draft_returned | withheld | interrupted | citation_verification_failed`). The pre-agent `query_blocked` 403 path still writes its own audit row with `action="query_blocked"` per the existing M2 shape — that path never constructs a `FinalDraftSection`. New optional sub-records live in `audit_log.generation.tool_calls: list[ToolCallRecord]` where `ToolCallRecord = {tool_name, started_at, duration_ms, input_hash, output_hash, model?, input_tokens?, output_tokens?}`. Hashed prompts/completions per ADR-0008 D3; raw citation IDs kept verbatim.

**Resume rows.** A `/resume` call writes its own audit row with `action="agent_resume"` and `outcome` equal to whatever the resumed agent terminates with. The row's `actor` block captures the resuming user (D8.1). Resume rows join to the original draft row via shared `run_id`, not via `request_id` (which is per-call).

**Backward compatibility.** Existing audit readers continue to see one row per `request_id`. The `tool_calls` field is inner detail; clients that ignore it see no change. The `run_id` field is new and additive.

**Why not one row per tool.** Multiple rows per request break the existing "1 request_id = 1 audit row" join semantics in the audit reader, and would force a schema-version bump (ADR-0008 D3 mandates explicit version bumps for breaking changes). One row + inner array is additive.

**Why not skip per-tool detail.** LangSmith captures per-tool detail in the trace, but LangSmith trace storage is plan-dependent and not under our retention control. Audit is the authoritative, on-tenant store; LangSmith is the developer-facing trace UI. Retention parity with ADR-0008 D3's existing FAR-4.805-analog 6-year floor is inherited automatically because the audit row format is unchanged — there is no new collection with a new retention story attached.

## Consequences

**Closes PRD §11 open questions.** "Gate implementation primitives + how a paused run is persisted across a multi-day human delay" — answered by D4 + D6. "Drafting UX: synchronous vs. streaming delivery" — answered by D8 as **synchronous + interrupt-resume**, streaming explicitly deferred.

**Does not pre-empt M3.** M3 is source-selection workflow (PRD §6 REQ-AGT-1..5). The agent harness, checkpointer, HITL middleware, and LangSmith wiring are reused for M3 with a different tool list (eval scoring, consensus, SSA decision). Nothing in D1–D9 makes M3 harder; D6's "interrupt on the gate-decision tool" generalizes directly to M3's FAR 15.308 SSA gate.

**Cost increase per section draft is bounded.** Net new model spend = two Nova Lite calls ≈ $0.0005 + zero programmatic-tool cost. The Sonnet call is unchanged from today; cost stays in the $0.04–$0.06/draft envelope.

**Net new Mongo collections.** `agent_checkpoints`, `agent_checkpoint_writes` — created automatically by `MongoDBSaver` on first write. No new index work beyond what the saver creates.

**Net new env vars.** `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` (D7) added to `.env.example`. All three optional — absence disables tracing without breaking the agent.

**Net new endpoint.** `POST /draft-solicitation/section/resume` (D8). Same per-tenant rate limiter (slowapi) applies.

**Carves out for Phase 2.** Streaming UX (D8), `langsmith` PII redaction beyond synthetic data (D7), audit-reader endpoint that surfaces `tool_calls` (D9), `MongoDBSaver` TTL/cleanup policy (D4).

**Explicit non-decisions (these remain open for later ADRs or specs).**
- Whether `extract_section_requirements` should use Nova Lite or Haiku — pricing fluctuates; the spec leaves the model ID as a config knob.
- Whether `retrieve_related_solicitations` should also rerank — initial implementation skips rerank for the related-solicitations tool to halve its Bedrock cost; observed quality decides.
- Whether the agent's system prompt should be FAR-section-specific or one shared prompt — initial implementation is one shared prompt with section_id as a structured input; we'll measure consistency on the eval gate.

**Watchwords this ADR deliberately does NOT smuggle in** (per `feedback_solo_adr_critic_pass.md`): no full app-side OpenTelemetry rollout (D7 limits LangSmith to in-agent only), no host-disk-encryption cohort prereq, no scheduled human-review time budget, no multi-tenant rollout beyond the retrieval boundary, no circuit-breaker work on the eval-service Mongo coupling, no AI-security hardening of legacy debt.
