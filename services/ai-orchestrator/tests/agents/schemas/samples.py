"""Canonical sample instances for every M1 schema (Phase 0, P0.1 tests).

One factory per model. Round-trip + extra-forbid tests parametrize over
``ALL_SAMPLES``. Keep each sample minimal-but-complete: every required field
populated, every Literal at an ADR-named value.
"""
from __future__ import annotations

from datetime import date, datetime

from app.agents import schemas as s

_DATE = date(2026, 6, 10)
_DT = datetime(2026, 6, 10, 12, 0, 0)


def _chunk() -> s.Chunk:
    return s.Chunk(
        chunk_id="far-15.204-5-001",
        text="Section L instructions ...",
        far_part="15",
        far_section="15.204-5",
        far_clause="52.215-1",
        snapshot_date=_DATE,
        relevance_score=0.91,
    )


def _citation() -> s.Citation:
    return s.Citation(
        chunk_id="far-15.204-5-001",
        far_part="15",
        far_section="15.204-5",
        far_clause="52.215-1",
        snapshot_date=_DATE,
        relevance_score=0.91,
        text="Section L instructions ...",
    )


def _pending_tool_call() -> s.PendingToolCall:
    return s.PendingToolCall(
        tool_name="compute_gate_decision",
        args={"rerank_top_score": 0.48},
        reason="rerank_top_score in [0.40, 0.55) — CO review required",
    )


def _final_draft_section() -> s.FinalDraftSection:
    return s.FinalDraftSection(
        outcome="draft_returned",
        section_text="The contractor shall ...",
        section_id="C",
        citations=[_citation()],
        gate_decision="pass",
        requires_human_review=False,
        rerank_top_score=0.91,
        request_id="req-001",
        run_id="sol-001:C:req-001",
        pending_tool_call=None,
        degraded_context=[],
    )


def _lm_alignment_report() -> s.LMAlignmentReport:
    return s.LMAlignmentReport(
        mismatches=[
            s.LMMismatch(
                type="weak_mapping",
                l_instruction="Submit past performance volume",
                m_factor=None,
                severity="warn",
                rationale="no M factor evaluates past performance",
            )
        ],
        overall_severity="warn",
        model="amazon.nova-lite-v1:0",
        input_tokens=120,
        output_tokens=64,
    )


def _set_aside_report() -> s.SetAsideConsistencyReport:
    return s.SetAsideConsistencyReport(
        mismatches=[
            s.SetAsideMismatch(
                set_aside="SDVOSB",
                expected_reps=["52.219-27"],
                actual_reps=[],
                missing=["52.219-27"],
                extra=[],
                severity="warn",
            )
        ],
        overall_severity="warn",
    )


def _clin_report() -> s.CLINCoverageReport:
    return s.CLINCoverageReport(
        gaps=[s.CLINGap(clin_id="0001", missing_in=["C"], severity="warn")],
        overall_severity="warn",
    )


def _part_iii_attachment() -> s.PartIIIAttachmentMeta:
    return s.PartIIIAttachmentMeta(
        title="Attachment 1 — Past performance questionnaire",
        date=_DATE,
        page_count=4,
        filename="att1.pdf",
    )


def _part_ii_clause_list() -> s.PartIIClauseList:
    return s.PartIIClauseList(
        clauses_by_reference=[
            s.FARClauseReference(
                citation="52.212-4",
                title="Contract Terms and Conditions — Commercial Products",
                prescription="FAR 12.301(b)(3)",
            )
        ],
        source="far_snapshot_index",
        snapshot_date=_DATE,
        resolved_for={"set_aside": "SDVOSB", "contract_type": "FFP", "agency_supplement": None},
    )


def _consistency_report() -> s.ConsistencyReport:
    return s.ConsistencyReport(
        solicitation_id="sol-001",
        run_id="sol-001:critic:req-001",
        lm_alignment=_lm_alignment_report(),
        set_aside_consistency=_set_aside_report(),
        clin_coverage=_clin_report(),
        overall_severity="warn",
        blocks_submit=False,
        model_used="amazon.nova-lite-v1:0",
        timestamp=_DT,
    )


ALL_SAMPLES: dict[str, object] = {
    "SectionPlanContext": s.SectionPlanContext(
        section_id="C",
        solicitation_id="sol-001",
        tenant_id="agency-test",
        naics="541512",
        set_aside="SDVOSB",
        contract_type="FFP",
        agency_supplement="GSAM",
        user_constraints="quarterly deliverable cadence",
        request_id="req-001",
        run_id="sol-001:C:req-001",
    ),
    "Chunk": _chunk(),
    "RetrievedEvidence": s.RetrievedEvidence(
        chunks=[_chunk()],
        vector_weight=0.6,
        fulltext_weight=0.4,
        rerank_top_score=0.91,
        degraded_mode=False,
    ),
    "SolicitationSummary": s.SolicitationSummary(
        solicitation_id="sol-000",
        title="Prior cloud migration BPA",
        naics="541512",
        set_aside="SDVOSB",
        contract_type="FFP",
        award_status="awarded",
        snapshot_date=_DATE,
    ),
    "RelatedSolicitations": s.RelatedSolicitations(
        summaries=[
            s.SolicitationSummary(
                solicitation_id="sol-000",
                title="Prior cloud migration BPA",
                naics="541512",
                set_aside="SDVOSB",
                contract_type="FFP",
                award_status="awarded",
                snapshot_date=_DATE,
            )
        ],
        count=1,
    ),
    "Requirement": s.Requirement(
        text="Deliverables shall be submitted quarterly",
        must_or_should="must",
        far_clause_hint=None,
        source_span=(0, 41),
    ),
    "ExtractedRequirements": s.ExtractedRequirements(
        requirements=[
            s.Requirement(
                text="Deliverables shall be submitted quarterly",
                must_or_should="must",
                far_clause_hint=None,
                source_span=(0, 41),
            )
        ],
        source_text_hash="ab12",
        model="amazon.nova-lite-v1:0",
        input_tokens=50,
        output_tokens=30,
    ),
    "ClaimCitation": s.ClaimCitation(
        sentence_index=0,
        chunk_id="far-15.204-5-001",
        far_clause="52.215-1",
        quote_span=(10, 60),
    ),
    "SectionDraftSkeleton": s.SectionDraftSkeleton(
        section_text="The contractor shall ...",
        claim_chunk_map=[s.ClaimCitation(sentence_index=0, chunk_id="far-15.204-5-001")],
        model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        input_tokens=900,
        output_tokens=400,
        completion_hash="cd34",
    ),
    "ValidationResult": s.ValidationResult(
        valid=True, unknown_chunk_ids=[], grounding_score=1.0
    ),
    "GateDecisionResult": s.GateDecisionResult(
        gate_decision="pass", rerank_top_score=0.91, reason="score >= pass threshold"
    ),
    "Citation": _citation(),
    "PendingToolCall": _pending_tool_call(),
    "FinalDraftSection": _final_draft_section(),
    "DraftSectionRequest": s.DraftSectionRequest(
        section_id="C",
        solicitation_id="sol-001",
        naics="541512",
        set_aside="SDVOSB",
        contract_type="FFP",
        agency_supplement="GSAM",
        query=None,
        constraints="quarterly deliverable cadence",
    ),
    "ResumeSectionRequest": s.ResumeSectionRequest(
        run_id="sol-001:C:req-001", decision="approve", edited_args=None, reason=None
    ),
    "AbandonSectionRequest": s.AbandonSectionRequest(
        run_id="sol-001:C:req-001", reason="CO typed manually"
    ),
    "PartIIIAttachmentMeta": _part_iii_attachment(),
    "BatchDraftRequest": s.BatchDraftRequest(
        solicitation_id="sol-001",
        naics="541512",
        set_aside="SDVOSB",
        contract_type="FFP",
        agency_supplement="GSAM",
        user_constraints_by_section={"C": "quarterly deliverable cadence"},
        provenances={"C": None, "H": None, "L": None, "M": None},
        part_iii_attachments=[_part_iii_attachment()],
    ),
    "FARClauseReference": s.FARClauseReference(
        citation="52.212-4",
        title="Contract Terms and Conditions — Commercial Products",
        prescription="FAR 12.301(b)(3)",
    ),
    "PartIIClauseList": _part_ii_clause_list(),
    "PartResult": s.PartResult(
        part="I",
        kind="llm_drafted",
        sections={"C": _final_draft_section(), "H": None},
    ),
    "PartDraftBundle": s.PartDraftBundle(
        part="I",
        sections={"C": _final_draft_section()},
        overall_outcome="draft_returned",
        pending_tool_call=None,
        rerank_top_score=0.91,
        request_id="req-001",
        run_id="sol-001:part_I:req-001",
    ),
    "LMMismatch": s.LMMismatch(
        type="l_without_m",
        l_instruction="Submit OCI mitigation plan",
        m_factor=None,
        severity="fail",
        rationale="no M factor evaluates OCI",
    ),
    "LMAlignmentReport": _lm_alignment_report(),
    "SetAsideMismatch": s.SetAsideMismatch(
        set_aside="SDVOSB",
        expected_reps=["52.219-27"],
        actual_reps=[],
        missing=["52.219-27"],
        extra=[],
        severity="warn",
    ),
    "SetAsideConsistencyReport": _set_aside_report(),
    "CLINGap": s.CLINGap(clin_id="0001", missing_in=["C", "F"], severity="fail"),
    "CLINCoverageReport": _clin_report(),
    "ConsistencyReport": _consistency_report(),
    "CriticRequest": s.CriticRequest(
        solicitation_id="sol-001",
        sections={"L": "Offerors shall ...", "M": "The Government will evaluate ..."},
        set_aside="SDVOSB",
    ),
    "SolicitationDraftBundle": s.SolicitationDraftBundle(
        solicitation_id="sol-001",
        parts={
            "I": s.PartResult(part="I", kind="llm_drafted", sections={"C": _final_draft_section()}),
            "II": s.PartResult(part="II", kind="programmatic_resolved", sections={"I": _part_ii_clause_list()}),
            "III": s.PartResult(part="III", kind="wizard_provided", sections={"J": [_part_iii_attachment()]}),
            "IV": s.PartResult(part="IV", kind="llm_drafted", sections={"L": _final_draft_section()}),
        },
        overall_outcome="batch_completed",
        consistency_report=_consistency_report(),
        pending_interrupts=[],
        request_id="req-001",
        batch_run_id="sol-001:batch:req-001",
    ),
    "BatchPerSectionDecision": s.BatchPerSectionDecision(
        section_id="L", decision="approve", edited_args=None, reason=None
    ),
    "BatchResumeRequest": s.BatchResumeRequest(
        batch_run_id="sol-001:batch:req-001",
        decisions=[s.BatchPerSectionDecision(section_id="L", decision="approve")],
    ),
    "PreflightResult": s.PreflightResult(
        ready=False,
        missing_required=["contract_type"],
        degraded_context=["agency_supplement"],
    ),
}
