"""P0.1 — serialize → deserialize → equality for every M1 schema.

Spec: docs/specs/m1-agentic-drafting/phases/0-foundation.md §6 P0.1.
"""
from __future__ import annotations

import json

import pytest

from app.agents import schemas as s

from .samples import ALL_SAMPLES

EXPECTED_MODELS = [
    "SectionPlanContext", "Chunk", "RetrievedEvidence", "SolicitationSummary",
    "RelatedSolicitations", "Requirement", "ExtractedRequirements", "ClaimCitation",
    "SectionDraftSkeleton", "ValidationResult", "GateDecisionResult", "Citation",
    "PendingToolCall", "FinalDraftSection", "DraftSectionRequest",
    "ResumeSectionRequest", "AbandonSectionRequest", "PartIIIAttachmentMeta",
    "BatchDraftRequest", "FARClauseReference", "PartIIClauseList", "PartResult",
    "PartDraftBundle", "LMMismatch", "LMAlignmentReport", "SetAsideMismatch",
    "SetAsideConsistencyReport", "CLINGap", "CLINCoverageReport",
    "ConsistencyReport", "CriticRequest", "SolicitationDraftBundle",
    "BatchPerSectionDecision", "BatchResumeRequest", "PreflightResult",
]


def test_every_tracker_named_model_has_a_sample():
    """Tracker §4 Phase 0 exit gate — every named model exists + is sampled."""
    for name in EXPECTED_MODELS:
        assert hasattr(s, name), f"schemas.py missing model {name}"
        assert name in ALL_SAMPLES, f"samples.py missing sample for {name}"


@pytest.mark.parametrize("name", sorted(ALL_SAMPLES))
def test_round_trip(name: str):
    sample = ALL_SAMPLES[name]
    model_cls = type(sample)
    # python-mode round trip
    rebuilt = model_cls.model_validate(sample.model_dump())
    assert rebuilt == sample
    # json-mode round trip (dates/datetimes/tuples cross the wire)
    rebuilt_json = model_cls.model_validate(json.loads(sample.model_dump_json()))
    assert rebuilt_json == sample


@pytest.mark.parametrize("name", sorted(ALL_SAMPLES))
def test_extra_fields_rejected(name: str):
    """extra='forbid' enforced on every model (spec §6.2 invariant)."""
    sample = ALL_SAMPLES[name]
    model_cls = type(sample)
    payload = sample.model_dump()
    payload["__unexpected_field__"] = "boom"
    with pytest.raises(Exception):
        model_cls.model_validate(payload)


def test_section_id_enum_has_no_i():
    """ADR-0012 D3 — section enum is A..M without I."""
    with pytest.raises(Exception):
        s.FinalDraftSection(
            outcome="withheld",
            section_id="I",
            gate_decision="withhold",
            requires_human_review=True,
            rerank_top_score=0.1,
            request_id="r",
            run_id="x:I:r",
        )


def test_consistency_report_blocks_submit_defaults_false():
    """Phase 1 invariant — warn-only critic."""
    sample = ALL_SAMPLES["ConsistencyReport"]
    assert sample.blocks_submit is False
    assert type(sample).model_fields["blocks_submit"].default is False
