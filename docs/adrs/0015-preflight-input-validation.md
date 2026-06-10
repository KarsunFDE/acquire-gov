# ADR 0015 — Preflight input validation: three-tier required-field policy + degraded_context surfacing

Date: 2026-06-10
Status: Proposed
Decision-makers: FDE pair (delivery lead + author)
Phase: 1 — AI Adoption · Milestone M1 (LLM-assisted solicitation drafting)
Related: ADR-0011 (security attack surface — QueryGuardrails baseline) · ADR-0012 (single-agent draft endpoint) · ADR-0013 (multi-agent topology) · ADR-0014 (per-AI-Part fan-out) · PRD §6 REQ-AID-1..4 · PRD §7 "grounded or withheld" · FAR 15.204-1..5

## Context

ADR-0012's `SectionDrafterAgent` and ADR-0014's `PartDrafterAgent` both consume metadata fields (`naics`, `set_aside`, `contract_type`, `agency_supplement`) without enforcing their presence. The tools degrade silently when those fields are null:

- `retrieve_related_solicitations` returns an empty result when both `naics` and `set_aside` are null (ADR-0012 D2 opportunistic skip — no Mongo call, no warning to user).
- `resolve_part_ii_clauses` returns an empty `PartIIClauseList` when `contract_type` is null (ADR-0014 D3 — Section I rendered as a blank list, no warning).
- `extract_section_requirements` returns empty `ExtractedRequirements` when `user_constraints` is null (intended — that field is genuinely optional).

The wizard contributes to the gap. Verified at 2026-06-10 against `frontend/src/app/components/solicitation-wizard/solicitation-wizard.component.ts:56-103`:

- Step 1 form uses **template-driven `[(ngModel)]`**, not reactive forms. **Zero `Validators.required`** on any of `title`, `agencyId`, `naics`, `setAside`, `contractType`, `noticeType`, `ceilingValue`, `description`.
- Next button at line 304: no `[disabled]` guard; advances with blank fields.
- AI-draft button at `section-card.component.ts:71`: only disabled while a draft is in flight; not gated on Step 1 completeness. The CO can click "AI-draft Section C" with no NAICS, no set-aside, no contract type set.
- `solicitation.service.ts:58-79` `draftSection()` posts only `{section_id, solicitation_id, query?, constraints?}`. NAICS / set-aside / contract type are **not in the request body**. There is no `X-Solicitation-Naics` header either.
- The backend cannot re-fetch the metadata from a solicitation record because the solicitation record is **not created until Step 13 submit** (per the wizard's existing ADR-0012 §12.5 flow). At AI-draft time the solicitation exists only as in-memory wizard state.

Net effect today: a CO who clicks AI-draft Section C immediately after entering Step 1 — even with every field blank — gets a 200 response with a section_text drafted on zero context. The agent's gate-decision tool may reject it on low rerank score (intended grounded-or-withheld behavior), but the underlying problem is that the agent never saw the context that would have made the retrieval relevant.

PRD §7 "authority over accuracy" + "grounded or withheld" both apply: the structural fix is to make required inputs explicit at the API boundary, not to rely on the agent's gate-decision threshold as a backstop for missing-input failures.

## Decisions

### D1 — Three-tier required-field policy

Required-field policy is **three tiers**, applied at the handler boundary before any agent is constructed:

| Tier | Action on missing | Field set (single-section endpoint) | Field set (batch endpoint) |
|---|---|---|---|
| **Hard-required** | 422 reject with `missing_required` field list | `tenant_id` (header), `solicitation_id`, `section_id`, `naics`, `set_aside`, `contract_type` | `tenant_id`, `solicitation_id`, `naics`, `set_aside`, `contract_type`, `agency_supplement`, at least one provenance ∈ {C,H,L,M} null |
| **Soft-required** | proceed; populate `degraded_context: list[str]` in response | `agency_supplement` (single-section), `naics` (for K/L/M only — for C/H it's hard) | — (all single-section soft-required fields are batch-hard-required) |
| **Optional** | proceed; no flag | `query`, `user_constraints`, `noticeType`, `ceilingValue`, `description` | `user_constraints_by_section`, `part_iii_attachments` |

**Why three tiers, not two.** A binary required/optional split forces a CO drafting an early-stage Section C SOW to either fill in agency_supplement (which she may legitimately not know yet — agency supplements like GSAM / DFARS / DEAR depend on funding source she's still negotiating) or wait. Soft-required captures the middle case: the field improves quality but doesn't structurally break drafting. The response surfaces a degraded_context warning so the CO can see what's been skipped without being blocked.

**Why naics is hard-required for C+H but soft for K+L+M.** Sections C (SOW) and H (special requirements) are domain-content-heavy — `retrieve_related_solicitations` filtering by NAICS is what surfaces prior agency SOWs with similar work types. Without NAICS, retrieval is generic and the drafted SOW is correspondingly generic. Sections K/L/M are about process (reps/certs, offeror instructions, evaluation factors) where NAICS is informational but not structurally required. The Pydantic validator applies the rule per section_id.

**Why contract_type is hard-required across all sections.** Section I clauses (Part II) are entirely determined by contract_type + set_aside + agency_supplement (ADR-0014 D3). If contract_type is null, Part II resolution returns empty — Section I gets a blank clause list, which is a defective solicitation. Better to 422 at the boundary than to ship a solicitation missing its core clause set.

### D2 — Preflight runs at handler entry (programmatic only, no LLM)

The preflight check is a **programmatic pre-handler step** that runs after `slowapi` rate-limit and `QueryGuardrails` (existing ADR-0011 D2 layers) and **before** the agent is constructed:

```python
# app/api/preflight.py — NEW
class PreflightResult(BaseModel):
    ready: bool
    missing_required: list[str] = []        # hard-required fields absent → caller gets 422
    degraded_context: list[str] = []         # soft-required fields absent → proceed with warning


HARD_REQUIRED_SINGLE = ["solicitation_id", "section_id", "contract_type"]
HARD_REQUIRED_SINGLE_CONTENT_SECTIONS = ["naics", "set_aside"]   # added for C, H
SOFT_REQUIRED_SINGLE = ["agency_supplement"]
HARD_REQUIRED_BATCH = ["solicitation_id", "naics", "set_aside", "contract_type", "agency_supplement"]


def preflight_single_section(request: DraftSectionRequest, tenant_id: str) -> PreflightResult:
    missing = [f for f in HARD_REQUIRED_SINGLE if getattr(request, f, None) in (None, "")]
    if request.section_id in {"C", "H"}:
        missing += [f for f in HARD_REQUIRED_SINGLE_CONTENT_SECTIONS
                    if getattr(request, f, None) in (None, "")]
    if not tenant_id:
        missing.append("tenant_id")   # belt-and-suspenders; ADR-0008 D2 already enforces at factory
    degraded = [f for f in SOFT_REQUIRED_SINGLE if getattr(request, f, None) in (None, "")]
    return PreflightResult(ready=not missing, missing_required=missing, degraded_context=degraded)


def preflight_batch(request: BatchDraftRequest, tenant_id: str) -> PreflightResult:
    missing = [f for f in HARD_REQUIRED_BATCH if getattr(request, f, None) in (None, "")]
    if not request.provenances or all(v is not None for v in request.provenances.values()):
        missing.append("at_least_one_null_provenance")
    if not tenant_id:
        missing.append("tenant_id")
    return PreflightResult(ready=not missing, missing_required=missing, degraded_context=[])
```

**Why programmatic.** PRD §10 cost-cap discipline + `feedback_solo_adr_critic_pass.md` watchword "goldplating." An LLM-based relevance check ("does user_constraints look like it's about Section C?") would add a Nova call per draft for marginal value when the next stage's grounding via rerank-and-gate already catches off-topic drafts via low scores. The right place for relevance enforcement is the gate-decision threshold (ADR-0012 D6), not a new LLM call upstream.

**Why before the agent is built.** Constructing `create_agent`, building tools, and creating a checkpoint thread for a request that's structurally invalid is wasteful and pollutes LangSmith / Mongo with no-op runs. 422 at the API boundary is the cheapest place to reject.

**Why preflight does NOT replace `QueryGuardrails`.** `QueryGuardrails` (ADR-0011 D2) catches jailbreak patterns, query-too-long, and (stubbed Nova-Micro) off-topic content. Preflight catches **structural input completeness**. The two run in sequence: rate-limit → guardrails (content safety) → preflight (input completeness) → agent.

### D3 — Single-section request body adds the metadata fields (additive-breaking)

`DraftSectionRequest` (ADR-0012 §4.1) is extended to carry the Step 1 metadata directly. The solicitation record does not exist at AI-draft time (created at Step 13 submit per the wizard flow); the backend cannot re-fetch. The request body is the only path:

```python
class DraftSectionRequest(BaseModel):
    section_id: Literal["A","B","C","D","E","F","G","H","J","K","L","M"]   # M2 _FAR_SECTION_ENUM
    solicitation_id: str = Field(min_length=1, max_length=128)

    # NEW — Step 1 metadata; required per D1's three-tier policy.
    naics: str | None = None
    set_aside: str | None = None
    contract_type: str | None = None
    agency_supplement: str | None = None

    query: str | None = Field(default=None, max_length=config.MAX_QUERY_CHARS)
    constraints: str | None = Field(default=None, max_length=1000)
```

The Pydantic schema marks the new fields as `str | None = None` because Pydantic-level validation cannot encode "required when section_id ∈ {C, H}, soft when section_id ∈ {K, L, M}" — that conditional logic lives in `preflight_single_section`. The 422 from preflight carries the field list so the wizard can highlight which inputs to fill.

**Why additive-breaking is OK here.** No external client of this endpoint exists yet — the ADR-0012 PRs (A1..F1) are not yet opened. Any breaking-shape decisions made before implementation lands cost nothing.

**Why not put the metadata in headers (X-Solicitation-Naics, etc.).** Headers are for transport / auth / tenancy — request semantics belong in the body. Section J attachment metadata (ADR-0014 D6.1) already established the precedent for body-carried solicitation context.

### D4 — Wizard Step 1 reactive-forms migration + AI-draft button gating

**Frontend changes** (in `frontend/src/app/components/solicitation-wizard/`):

1. **Convert Step 1 to reactive forms.** Replace `[(ngModel)]` with `FormGroup` + `FormControl` + `Validators.required` on the 5 hard-required fields (`title`, `agency_id`, `naics`, `setAside`, `contractType`). Optional Step 1 fields (`noticeType`, `ceilingValue`, `description`) stay validator-free.
2. **Next-button gate.** Bind `[disabled]` on Step 1's "Next" button to `!step1Form.valid`.
3. **AI-draft button gate.** `section-card.component.ts:71` button gets `[disabled]="drafting || !isStep1ContextReady()"`. `isStep1ContextReady()` is passed from the wizard parent component (the parent owns the Step 1 form; the section-card is a child component).
4. **Inline degraded-context warnings.** When the wizard receives a 200 response with `degraded_context` populated, render a yellow inline banner on the section-card: "Drafted without {field, field}. Retrieval quality may be lower; consider filling these and re-drafting."

**Why reactive forms.** Angular template-driven forms can be made required-aware via `required` attribute + `#form="ngForm"`, but reactive forms give us a single form-validity signal (`.valid`) the section-card child can consume without `@Input` proliferation. The codebase is mixed; per CLAUDE.md "don't backwards-compat-hack," we migrate cleanly to reactive.

**Why not validate everything on a single "Submit for review" gate at Step 13.** The cost of an AI-draft on missing context is a wasted ~$0.05 + a Mongo checkpoint that never gets used + the CO's time looking at a generic draft. Cheaper to block at the button than to remediate at submit.

### D5 — `degraded_context` is an additive field on `FinalDraftSection`

`FinalDraftSection` (ADR-0012 D3 + ADR-0014) gains:

```python
class FinalDraftSection(BaseModel):
    # ... existing ADR-0012 fields ...
    degraded_context: list[str] = Field(default_factory=list)
```

Populated by the handler from the preflight `degraded_context` list. The agent itself does not read or write this field; it's handler-level metadata that the wizard surfaces to the CO.

**Why additive.** ADR-0012 D3 `model_config = ConfigDict(extra="forbid")`; adding a new field with a default is the only way to extend without breaking field-strict consumers. Existing field types and outcome enum are unchanged.

### D6 — Audit row carries preflight outcome

The existing `audit_log` row (ADR-0008 D3 schema preserved) gets one new optional sub-field:

```python
{
    ...standard ADR-0008 D3 fields...,
    "preflight": {
        "ready": true,
        "missing_required": [],
        "degraded_context": ["agency_supplement"],   # when D1 soft-required hit
    },
}
```

422-rejected requests still write an audit row with `action="preflight_rejected"`, `outcome="preflight_rejected"`, and the `missing_required` list. The 422 is observable in audit replay; "blank draft attempted without NAICS" is not silent.

**Why audit even on rejected requests.** Adversarial pattern detection — if a tenant repeatedly hits `/draft-solicitation/section` with `missing_required=["naics","set_aside","contract_type"]`, that's a signal of a misbehaving client OR a probe pattern that the synthetic-data CI gate (`m2-grounded-retrieval/eval-harness.md`) can flag.

### D7 — Backward compatibility + migration

The new fields are added before any implementation PR opens (per ADR-0012 §15 — A1..F1 not yet started). The cohort lands the preflight check as part of the existing rollout slot:

- **ADR-0012 spec §15 PR D1** (the `api/draft.py` rewrite) absorbs the new `DraftSectionRequest` shape + preflight call.
- **ADR-0014 spec §18.12 PR I3** (the `/batch` + `/batch/resume` endpoints) absorbs the batch preflight.
- **ADR-0012 spec §15 PR F1** (frontend) absorbs the reactive-forms migration + button gates.

No new rollout slots required. Net impact: ~1 extra implementer-day across D1 + I3 + F1.

## Consequences

**Closes the user's 2026-06-10 follow-up on input validation.** Three-tier policy + preflight handler step + request-body extension + wizard reactive-forms gating + `degraded_context` response field cover the four gaps verified at the start of this ADR.

**Net new contracts.**

- `DraftSectionRequest` gains 4 nullable fields (`naics`, `set_aside`, `contract_type`, `agency_supplement`).
- `BatchDraftRequest` keeps its ADR-0014 shape (already carries all the metadata fields).
- `FinalDraftSection` gains `degraded_context: list[str]`.
- `audit_log` row gains optional `preflight` sub-record.
- New 422 outcomes: `preflight_rejected_missing_required` (single-section), `preflight_rejected_batch_missing_required` (batch).
- New PreflightResult Pydantic + two `preflight_*` functions (`app/api/preflight.py`).

**No new endpoints. No new agents. No new tools.** The preflight check is a thin pre-handler stage — cheapest possible add.

**Cost.** Preflight is programmatic; zero LLM cost. Wizard reactive-forms migration is one-time frontend work; runtime cost is zero. Audit row size grows by ~50 bytes per row on average (the new `preflight` sub-record).

**Wizard impact.** Reactive-forms migration is a Step 1 component change + a parent-to-child `[isStep1Ready]` input propagation to `section-card`. No other component changes. Section 12 critic surface unchanged.

**Carves out for Phase 2 / M3.** LLM-based relevance check on `user_constraints` (explicitly out of scope per D2 — goldplating). Solicitation pre-create at Step 1 instead of Step 13 (would let the backend re-fetch metadata; bigger workflow change deferred). Per-tenant override of the hard-required field set (currently global config).

**Watchwords this ADR deliberately does NOT smuggle in** (per `feedback_solo_adr_critic_pass.md`): no app-side OTel rollout, no scheduled human-review time budget, no LLM-classified validation, no managed Bedrock products, no cross-tenant validation beyond the existing ADR-0008 D2 boundary, no AI-security hardening of the legacy debt (the wizard's template-driven form is brownfield debt-adjacent — D4 migrates it because it's the load-bearing fix, not as a wider modernization push).

**Explicit non-decisions.**

- Whether `noticeType` or `ceilingValue` should be hard-required for a given section — out of scope; both are optional in Phase 1 because they don't feed retrieval / clause selection.
- Whether `agency_supplement` should be promoted to hard-required if Section I clauses for the agency in question depend on a specific supplement — handled inside `resolve_part_ii_clauses` (ADR-0014 D3) via a "no supplement-specific clauses found" warning; not promoted to preflight blocker.
- Whether to support partial-fill saves of Step 1 (CO fills NAICS, comes back tomorrow) — orthogonal; the wizard's existing component-state persistence covers this until a solicitation record exists.
