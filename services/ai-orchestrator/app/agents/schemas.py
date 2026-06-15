"""M1 agentic-drafting Pydantic models — single source of truth (Phase 0, P0.1).

Sources:
- ADR-0012 D3  — section-drafter schemas (SectionPlanContext .. FinalDraftSection)
- ADR-0013 D6  — batch/critic schemas (ConsistencyReport + sub-reports, CriticRequest)
- ADR-0014 D6+D9 — per-FAR-Part fan-out (PartDraftBundle, PartResult, PartIIClauseList,
  PartIIIAttachmentMeta, FARClauseReference, superseded BatchDraftRequest/SolicitationDraftBundle)
- ADR-0015 D3+D5 — preflight (PreflightResult, DraftSectionRequest metadata fields,
  FinalDraftSection.degraded_context)

Full design reference: docs/specs/m1-agentic-drafting/design-reference.md §6.2, §18.2,
§18.12.2, §19.2.

Invariant: every model carries ``model_config = ConfigDict(extra="forbid")`` so
unknown fields raise at the boundary instead of silently passing downstream.
"""
from __future__ import annotations

from datetime import date, datetime
from datetime import date as _Date  # alias — PartIIIAttachmentMeta has a field named `date`
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app import config

SectionId = Literal["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M"]


# ---------------------------------------------------------------------------
# ADR-0012 D3 — section-drafter pipeline models
# ---------------------------------------------------------------------------


class SectionPlanContext(BaseModel):
    """Initial agent state assembled by the handler from the preflight-validated
    request (design ref topology stage 0b)."""

    model_config = ConfigDict(extra="forbid")

    section_id: SectionId
    solicitation_id: str = Field(min_length=1, max_length=128)
    tenant_id: str
    naics: str | None = None
    set_aside: str | None = None
    contract_type: str | None = None        # NEW per ADR-0015 D3
    agency_supplement: str | None = None    # NEW per ADR-0015 D3
    user_constraints: str | None = Field(default=None, max_length=1000)
    request_id: str
    run_id: str  # = f"{solicitation_id}:{section_id}:{request_id}"


class Chunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    text: str
    far_part: str
    far_section: str
    far_clause: str | None
    snapshot_date: date
    relevance_score: float


class RetrievedEvidence(BaseModel):
    """Output of retrieve_far_clauses. ``gate_decision`` is deliberately NOT a
    field here — it is produced by compute_gate_decision so the HITL middleware
    has a tool whose input args fully determine its return (ADR-0012 D6)."""

    model_config = ConfigDict(extra="forbid")

    chunks: list[Chunk]
    vector_weight: float
    fulltext_weight: float
    rerank_top_score: float | None  # None == rerank outage / passthrough
    degraded_mode: bool = False


class SolicitationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solicitation_id: str
    title: str
    naics: str | None
    set_aside: str | None
    contract_type: str | None
    award_status: Literal["internal_review", "published", "awarded", "cancelled"]
    snapshot_date: date


class RelatedSolicitations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summaries: list[SolicitationSummary]
    count: int


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    must_or_should: Literal["must", "should"]
    far_clause_hint: str | None
    source_span: tuple[int, int]


class ExtractedRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    requirements: list[Requirement]
    source_text_hash: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class ClaimCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentence_index: int = Field(ge=0)
    chunk_id: str
    far_clause: str | None = None
    quote_span: tuple[int, int] | None = None


class SectionDraftSkeleton(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    section_text: str = Field(min_length=1)
    claim_chunk_map: list[ClaimCitation]
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    completion_hash: str


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    unknown_chunk_ids: list[str]
    grounding_score: float = Field(ge=0.0, le=1.0)


class GateDecisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate_decision: Literal["pass", "hitl", "withhold", "rerank_unavailable_passthrough"]
    rerank_top_score: float | None
    reason: str


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    far_part: str
    far_section: str
    far_clause: str | None
    snapshot_date: date
    relevance_score: float
    text: str


class PendingToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str  # "compute_gate_decision"
    args: dict      # echo of the args the middleware blocked on
    reason: str     # "rerank_top_score in [{w_t}, {p_t}) — CO review required"


class FinalDraftSection(BaseModel):
    """The section-drafter agent's ``response_format`` (ADR-0012 D3)."""

    model_config = ConfigDict(extra="forbid")

    outcome: Literal[
        "draft_returned", "withheld", "interrupted", "citation_verification_failed"
    ]
    section_text: str | None = None  # populated iff outcome == "draft_returned"
    section_id: SectionId
    citations: list[Citation] = Field(default_factory=list)
    gate_decision: Literal["pass", "hitl", "withhold", "rerank_unavailable_passthrough"]
    requires_human_review: bool
    rerank_top_score: float | None
    request_id: str
    run_id: str  # = f"{solicitation_id}:{section_id}:{request_id}"
    pending_tool_call: PendingToolCall | None = None  # populated iff outcome=="interrupted"
    degraded_context: list[str] = Field(default_factory=list)  # NEW per ADR-0015 D5


# ---------------------------------------------------------------------------
# ADR-0012 D8 — request bodies for /section, /section/resume, /section/abandon
# ---------------------------------------------------------------------------


class DraftSectionRequest(BaseModel):
    """``POST /draft-solicitation/section`` body (design ref §4.1 + §19.4)."""

    model_config = ConfigDict(extra="forbid")

    section_id: SectionId
    solicitation_id: str = Field(min_length=1, max_length=128)

    # NEW per ADR-0015 D3 — Step 1 metadata; tier-validated by preflight, not Pydantic.
    naics: str | None = None
    set_aside: str | None = None
    contract_type: str | None = None
    agency_supplement: str | None = None
    # DEMO-REDESIGN-spec §4 — optional richer context (mirrors BatchDraftRequest).
    period_of_performance: str | None = Field(default=None, max_length=300)
    place_of_performance: str | None = Field(default=None, max_length=300)
    eval_approach: str | None = None
    key_personnel: str | None = Field(default=None, max_length=500)

    query: str | None = Field(default=None, max_length=config.MAX_QUERY_CHARS)
    constraints: str | None = Field(default=None, max_length=1000)


class ResumeSectionRequest(BaseModel):
    """``POST /draft-solicitation/section/resume`` body (design ref §4.2)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    decision: Literal["approve", "edit", "reject"]
    edited_args: dict | None = None  # required when decision == "edit"
    reason: str | None = Field(default=None, max_length=500)


class AbandonSectionRequest(BaseModel):
    """``POST /draft-solicitation/section/abandon`` body (design ref §4.3)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    reason: str | None = Field(default=None, max_length=200)


# ---------------------------------------------------------------------------
# ADR-0014 D6 — per-FAR-Part batch fan-out models (supersedes ADR-0013 D6.1)
# ---------------------------------------------------------------------------


class PartIIIAttachmentMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    date: _Date | None = None
    page_count: int | None = Field(default=None, ge=0)
    filename: str | None = None


class BatchDraftRequest(BaseModel):
    """``POST /draft-solicitation/batch`` body (design ref §18.12.2)."""

    model_config = ConfigDict(extra="forbid")

    solicitation_id: str = Field(min_length=1, max_length=128)
    naics: str | None = None
    set_aside: str | None = None
    contract_type: str | None = None       # NEW per ADR-0014 D3 (Part II clause resolution)
    agency_supplement: str | None = None   # NEW per ADR-0014 D3
    # DEMO-REDESIGN-spec §4 — richer draft context (all optional/soft).
    period_of_performance: str | None = Field(default=None, max_length=300)
    place_of_performance: str | None = Field(default=None, max_length=300)
    eval_approach: str | None = None       # "LPTA" | "TRADEOFF"
    key_personnel: str | None = Field(default=None, max_length=500)
    user_constraints_by_section: dict[Literal["C", "H", "L", "M"], str] = Field(
        default_factory=dict
    )
    provenances: dict[SectionId, str | None] = Field(default_factory=dict)
    part_iii_attachments: list[PartIIIAttachmentMeta] = Field(default_factory=list)


class FARClauseReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation: str       # e.g. "52.212-4"
    title: str
    prescription: str   # e.g. "FAR 12.301(b)(3)"


class PartIIClauseList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clauses_by_reference: list[FARClauseReference]
    source: Literal["far_snapshot_index"]
    snapshot_date: date
    resolved_for: dict[str, str | None]


class PartResult(BaseModel):
    """One FAR-UCF-Part result inside a SolicitationDraftBundle.

    ``sections`` is keyed by section_id. AI-drafted sections (C, H in Part I;
    L, M in Part IV) hold FinalDraftSection. Section I holds PartIIClauseList.
    Section J holds the per-attachment metadata list (wizard passthrough)."""

    model_config = ConfigDict(extra="forbid")

    part: Literal["I", "II", "III", "IV"]
    kind: Literal["llm_drafted", "programmatic_resolved", "wizard_provided"]
    sections: dict[
        str,
        FinalDraftSection | PartIIClauseList | list[PartIIIAttachmentMeta] | None,
    ]


class PartDraftBundle(BaseModel):
    """Structured output of a PartDrafterAgent run (ADR-0014 D6)."""

    model_config = ConfigDict(extra="forbid")

    part: Literal["I", "IV"]
    sections: dict[str, FinalDraftSection]  # "C","H" for Part I; "L","M" for Part IV
    overall_outcome: Literal[
        "draft_returned", "withheld", "interrupted", "citation_verification_failed"
    ]
    pending_tool_call: PendingToolCall | None = None
    rerank_top_score: float | None
    request_id: str
    run_id: str  # = f"{sol_id}:part_{part}:{request_id}"


# ---------------------------------------------------------------------------
# ADR-0013 D6.3 — consistency-critic models
# ---------------------------------------------------------------------------


class LMMismatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["l_without_m", "m_without_l", "weak_mapping"]
    # Defaults: model-facing via the critic tool — Nova Lite omits null
    # fields entirely instead of emitting them.
    l_instruction: str | None = None
    m_factor: str | None = None
    severity: Literal["info", "warn", "fail"]
    rationale: str


class LMAlignmentReport(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    mismatches: list[LMMismatch]
    overall_severity: Literal["info", "warn", "fail"]
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class SetAsideMismatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    set_aside: str
    expected_reps: list[str]
    actual_reps: list[str]
    missing: list[str]
    extra: list[str]
    severity: Literal["info", "warn", "fail"]


class SetAsideConsistencyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mismatches: list[SetAsideMismatch]
    overall_severity: Literal["info", "warn", "fail"]


class CLINGap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clin_id: str
    missing_in: list[Literal["C", "F", "L"]]
    severity: Literal["info", "warn", "fail"]


class CLINCoverageReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gaps: list[CLINGap]
    overall_severity: Literal["info", "warn", "fail"]


class ConsistencyReport(BaseModel):
    """The consistency-critic agent's ``response_format`` (ADR-0013 D4).

    Phase 1 invariant: ``blocks_submit`` is always False (warn-only critic)."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    solicitation_id: str
    run_id: str
    lm_alignment: LMAlignmentReport
    set_aside_consistency: SetAsideConsistencyReport
    clin_coverage: CLINCoverageReport
    overall_severity: Literal["info", "warn", "fail"]
    blocks_submit: bool = False  # Phase 1 = always False
    model_used: str | None = None
    timestamp: datetime
    # KNOWN ISSUE (2026-06-12): Nova Lite re-invokes the critic tools forever
    # instead of emitting this report (CRITIC_RECURSION_LIMIT bounds the run).
    # When the agent fails, callers return a skipped report instead of dying —
    # the UI must tell the CO to review manually.
    critic_skipped: bool = False
    skip_reason: str | None = None


class CriticRequest(BaseModel):
    """``POST /draft-solicitation/critic`` body (ADR-0013 D6.2)."""

    model_config = ConfigDict(extra="forbid")

    solicitation_id: str = Field(min_length=1, max_length=128)
    sections: dict[SectionId, str | None]
    set_aside: str | None = None


# ---------------------------------------------------------------------------
# ADR-0013 D6.1 — batch bundle + resume (bundle shape superseded by ADR-0014)
# ---------------------------------------------------------------------------


class SolicitationDraftBundle(BaseModel):
    """``POST /draft-solicitation/batch`` response (design ref §18.12.2)."""

    model_config = ConfigDict(extra="forbid")

    solicitation_id: str
    parts: dict[Literal["I", "II", "III", "IV"], PartResult]
    overall_outcome: Literal["batch_completed", "batch_interrupted"]
    consistency_report: ConsistencyReport | None
    pending_interrupts: list[PendingToolCall] = Field(default_factory=list)
    request_id: str
    batch_run_id: str  # = f"{solicitation_id}:batch:{request_id}"


class BatchPerSectionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: Literal["C", "H", "L", "M"]
    decision: Literal["approve", "edit", "reject"]
    edited_args: dict | None = None
    reason: str | None = Field(default=None, max_length=500)


class BatchResumeRequest(BaseModel):
    """``POST /draft-solicitation/batch/resume`` body (ADR-0013 D6.1)."""

    model_config = ConfigDict(extra="forbid")

    batch_run_id: str
    decisions: list[BatchPerSectionDecision]


# ---------------------------------------------------------------------------
# ADR-0015 D5 — preflight result
# ---------------------------------------------------------------------------


class PreflightResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    missing_required: list[str] = Field(default_factory=list)
    degraded_context: list[str] = Field(default_factory=list)
