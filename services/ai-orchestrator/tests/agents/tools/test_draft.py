"""P1.3 — draft_section_text stubbed-LLM tests (design ref §13.1)."""
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
from app.agents.tools.draft import _DraftPayload, draft_section_text


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


def _run():
    return draft_section_text.func(  # type: ignore[attr-defined]
        section_id="C",
        evidence=_evidence(),
        requirements=_reqs(),
        related=_related(),
        config={"configurable": {"tenant_id": "tenant_A"}},
    )


def test_happy_path_produces_skeleton(monkeypatch):
    payload = _DraftPayload(
        section_text="The contractor shall ...",
        claim_chunk_map=[ClaimCitation(sentence_index=0, chunk_id="c1")],
    )
    raw = SimpleNamespace(usage_metadata={"input_tokens": 900, "output_tokens": 400})
    captured = _wire(monkeypatch, {"parsed": payload, "raw": raw, "parsing_error": None})
    result = _run()
    assert result.section_text == "The contractor shall ..."
    assert result.claim_chunk_map[0].chunk_id == "c1"
    assert result.input_tokens == 900
    assert result.completion_hash
    # ADR-0011 D1.2 — delimiter wrap present in the prompt.
    user_msg = captured["prompt"][1]["content"]
    assert '<retrieved_context type="far_data" trust_level="reference_only">' in user_msg
    assert "</retrieved_context>" in user_msg
    assert "chunk_id=c1" in user_msg


def test_malformed_structured_output_raises_draft_parse_failed(monkeypatch):
    raw = SimpleNamespace(usage_metadata={})
    _wire(monkeypatch, {"parsed": None, "raw": raw, "parsing_error": "bad json"})
    with pytest.raises(ValueError, match="draft_parse_failed"):
        _run()
