"""P1.3 — extract_section_requirements stubbed-LLM tests (design ref §13.1)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.agents.tools import extract_requirements as er_mod
from app.agents.tools.extract_requirements import (
    _ExtractPayload,
    extract_section_requirements,
)
from app.agents.schemas import Requirement


def _payload() -> _ExtractPayload:
    return _ExtractPayload(
        requirements=[
            Requirement(
                text="Deliverables shall be quarterly",
                must_or_should="must",
                far_clause_hint=None,
                source_span=(0, 31),
            )
        ]
    )


def _wire(monkeypatch, results: list):
    """Each call to extractor.invoke pops the next canned result."""
    invoke_mock = MagicMock(side_effect=results)
    extractor = SimpleNamespace(invoke=invoke_mock)
    chat = SimpleNamespace(with_structured_output=lambda *_a, **_kw: extractor)
    monkeypatch.setattr(er_mod, "_extract_chat", lambda: chat)
    return invoke_mock


def _run(constraints, section_id="C"):
    return extract_section_requirements.func(  # type: ignore[attr-defined]
        user_constraints=constraints, section_id=section_id
    )


def test_null_constraints_no_bedrock_call(monkeypatch):
    invoke_mock = _wire(monkeypatch, [])
    result = _run(None)
    assert result.requirements == []
    assert result.input_tokens == 0
    invoke_mock.assert_not_called()


def test_happy_path(monkeypatch):
    raw = SimpleNamespace(usage_metadata={"input_tokens": 50, "output_tokens": 30})
    _wire(monkeypatch, [{"parsed": _payload(), "raw": raw, "parsing_error": None}])
    result = _run("quarterly deliverables")
    assert len(result.requirements) == 1
    assert result.requirements[0].must_or_should == "must"
    assert result.input_tokens == 50
    assert result.source_text_hash  # sha256 of constraints


def test_retries_once_then_succeeds(monkeypatch):
    raw = SimpleNamespace(usage_metadata={})
    invoke_mock = _wire(monkeypatch, [
        {"parsed": None, "raw": raw, "parsing_error": "malformed"},
        {"parsed": _payload(), "raw": raw, "parsing_error": None},
    ])
    result = _run("quarterly deliverables")
    assert invoke_mock.call_count == 2  # BEDROCK_EXTRACT_MAX_RETRIES=1 → 2 attempts
    assert len(result.requirements) == 1


def test_degrades_to_empty_after_retry_exhaustion(monkeypatch):
    raw = SimpleNamespace(usage_metadata={})
    invoke_mock = _wire(monkeypatch, [
        {"parsed": None, "raw": raw, "parsing_error": "malformed"},
        {"parsed": None, "raw": raw, "parsing_error": "still malformed"},
    ])
    result = _run("quarterly deliverables")
    assert invoke_mock.call_count == 2
    assert result.requirements == []          # degraded fallback, no raise
    assert result.source_text_hash            # hash still recorded
