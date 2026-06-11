"""P1.3 + P3.1 — draft_section_text stubbed-LLM tests.

Phase 3 (ADR-0014 PR I0) made the tool list-based: singleton-list invocation
preserves the Phase 1 single-section contract; multi-section invocation emits
one skeleton per section from a single Sonnet call.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.agents.schemas import (
    Chunk,
    ClaimCitation,
    ExtractedRequirements,
    RelatedSolicitations,
    RetrievedEvidence,
)
from app.agents.tools import draft as draft_tool_mod
from app.agents.tools.draft import (
    _DraftPayload,
    _MultiDraftPayload,
    draft_section_text,
)


def _evidence() -> RetrievedEvidence:
    return RetrievedEvidence(
        chunks=[
            Chunk(
                chunk_id="c1",
                text="FAR text",
                far_part="15",
                far_section="15.204-5",
                far_clause=None,
                snapshot_date=date(2026, 6, 9),
                relevance_score=0.9,
            )
        ],
        vector_weight=1.0,
        fulltext_weight=1.0,
        rerank_top_score=0.9,
    )


def _reqs() -> ExtractedRequirements:
    return ExtractedRequirements(
        requirements=[], source_text_hash="", model="m", input_tokens=0, output_tokens=0
    )


def _related() -> RelatedSolicitations:
    return RelatedSolicitations(summaries=[], count=0)


def _payload(text: str) -> _DraftPayload:
    return _DraftPayload(
        section_text=text,
        claim_chunk_map=[ClaimCitation(sentence_index=0, chunk_id="c1")],
    )


def _wire(monkeypatch, result: dict):
    captured = {}

    def _invoke(prompt):
        captured["prompt"] = prompt
        return result

    chat = SimpleNamespace(
        with_structured_output=lambda *_a, **_kw: SimpleNamespace(invoke=_invoke)
    )
    monkeypatch.setattr(draft_tool_mod, "_draft_chat", lambda: chat)
    return captured


def _run(section_ids: list[str]):
    return draft_section_text.func(  # type: ignore[attr-defined]
        section_ids=section_ids,
        evidence=_evidence(),
        requirements=_reqs(),
        related=_related(),
        config={"configurable": {"tenant_id": "tenant_A"}},
    )


def test_singleton_list_preserves_single_section_contract(monkeypatch):
    parsed = _MultiDraftPayload(sections={"C": _payload("The contractor shall ...")})
    raw = SimpleNamespace(usage_metadata={"input_tokens": 900, "output_tokens": 400})
    captured = _wire(monkeypatch, {"parsed": parsed, "raw": raw, "parsing_error": None})
    result = _run(["C"])
    assert set(result) == {"C"}
    skel = result["C"]
    assert skel.section_text == "The contractor shall ..."
    assert skel.claim_chunk_map[0].chunk_id == "c1"
    assert skel.input_tokens == 900
    assert skel.completion_hash
    # ADR-0011 D1.2 — delimiter wrap present in the prompt.
    user_msg = captured["prompt"][1]["content"]
    assert '<retrieved_context type="far_data" trust_level="reference_only">' in user_msg
    assert "chunk_id=c1" in user_msg


def test_multi_section_emits_one_skeleton_per_section(monkeypatch):
    parsed = _MultiDraftPayload(
        sections={"C": _payload("C text"), "H": _payload("H text")}
    )
    raw = SimpleNamespace(usage_metadata={"input_tokens": 1000, "output_tokens": 600})
    captured = _wire(monkeypatch, {"parsed": parsed, "raw": raw, "parsing_error": None})
    result = _run(["C", "H"])
    assert set(result) == {"C", "H"}
    assert result["C"].section_text == "C text"
    assert result["H"].section_text == "H text"
    # Token usage attributed once (no double count across skeletons).
    assert result["C"].input_tokens == 1000
    assert result["H"].input_tokens == 0
    # Coherence steering present for multi-section calls.
    assert "draft them coherently" in captured["prompt"][1]["content"]


def test_malformed_structured_output_raises_draft_parse_failed(monkeypatch):
    raw = SimpleNamespace(usage_metadata={})
    _wire(monkeypatch, {"parsed": None, "raw": raw, "parsing_error": "bad json"})
    with pytest.raises(ValueError, match="draft_parse_failed"):
        _run(["C"])


def test_missing_requested_section_raises_typed_error(monkeypatch):
    parsed = _MultiDraftPayload(sections={"C": _payload("C only")})
    raw = SimpleNamespace(usage_metadata={})
    _wire(monkeypatch, {"parsed": parsed, "raw": raw, "parsing_error": None})
    with pytest.raises(ValueError, match="omitted section"):
        _run(["C", "H"])
