"""P4.1 — per-tool critic unit tests (design ref §18.8)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import config
from app.agents.critic.tools import lm_consistency as lm_mod
from app.agents.critic.tools.clin_coverage import check_clin_coverage
from app.agents.critic.tools.lm_consistency import verify_l_m_consistency
from app.agents.critic.tools.set_aside import (
    SET_ASIDE_REQUIRED_CLAUSES,
    check_set_aside_consistency,
)
from app.agents.schemas import LMAlignmentReport, LMMismatch


# ---------------------------------------------------------------------------
# verify_l_m_consistency (LLM — stubbed chat)
# ---------------------------------------------------------------------------


def _wire_lm(monkeypatch, result: dict):
    chat = SimpleNamespace(
        with_structured_output=lambda *_a, **_kw: SimpleNamespace(
            invoke=lambda prompt: result
        )
    )
    monkeypatch.setattr(lm_mod, "_critic_chat", lambda: chat)


def _lm(section_l, section_m):
    return verify_l_m_consistency.func(  # type: ignore[attr-defined]
        section_l=section_l, section_m=section_m
    )


def test_lm_missing_section_skips_semantic_check(monkeypatch):
    def _boom():
        raise AssertionError("no LLM call when a section is missing")

    monkeypatch.setattr(lm_mod, "_critic_chat", _boom)
    report = _lm("L text", None)
    assert report.overall_severity == "info"
    assert report.mismatches[0].type == "l_without_m"
    report2 = _lm(None, "M text")
    assert report2.mismatches[0].type == "m_without_l"


def test_lm_happy_path_fills_usage(monkeypatch):
    parsed = LMAlignmentReport(
        mismatches=[
            LMMismatch(type="weak_mapping", l_instruction="submit PPQ",
                       m_factor=None, severity="warn",
                       rationale="no factor evaluates past performance")
        ],
        overall_severity="warn", model="tool-filled", input_tokens=0, output_tokens=0,
    )
    raw = SimpleNamespace(usage_metadata={"input_tokens": 200, "output_tokens": 90})
    _wire_lm(monkeypatch, {"parsed": parsed, "raw": raw, "parsing_error": None})
    report = _lm("L text", "M text")
    assert report.overall_severity == "warn"
    assert report.model == config.BEDROCK_CRITIC_MODEL
    assert report.input_tokens == 200


def test_lm_malformed_output_propagates(monkeypatch):
    """Single-pass critic — no retry fallback (design ref §18.8)."""
    raw = SimpleNamespace(usage_metadata={})
    _wire_lm(monkeypatch, {"parsed": None, "raw": raw, "parsing_error": "bad"})
    with pytest.raises(ValueError, match="critic_parse_failed"):
        _lm("L text", "M text")


# ---------------------------------------------------------------------------
# check_set_aside_consistency (programmatic — table-driven)
# ---------------------------------------------------------------------------


def _sa(set_aside, section_k):
    return check_set_aside_consistency.func(  # type: ignore[attr-defined]
        set_aside=set_aside, section_k_text=section_k
    )


@pytest.mark.parametrize("set_aside", sorted(SET_ASIDE_REQUIRED_CLAUSES))
def test_set_aside_matched_is_info(set_aside):
    required = sorted(SET_ASIDE_REQUIRED_CLAUSES[set_aside])
    section_k = "\n".join(f"K.x FAR {c} incorporated by reference" for c in required)
    report = _sa(set_aside, section_k)
    assert report.overall_severity == "info"
    assert report.mismatches[0].missing == []


@pytest.mark.parametrize("set_aside", sorted(SET_ASIDE_REQUIRED_CLAUSES))
def test_set_aside_missing_required_is_warn(set_aside):
    report = _sa(set_aside, "K.1 52.204-7 SAM registration only")
    assert report.overall_severity == "warn"
    assert report.mismatches[0].missing == sorted(SET_ASIDE_REQUIRED_CLAUSES[set_aside])


def test_set_aside_extra_info_only_by_default(monkeypatch):
    monkeypatch.setattr(config, "SET_ASIDE_STRICT_EXTRA", False)
    section_k = "FAR 52.219-27 plus extra 52.219-6 rep"
    report = _sa("SDVOSB", section_k)
    assert report.overall_severity == "info"
    assert report.mismatches[0].extra == []


def test_set_aside_extra_warns_when_strict(monkeypatch):
    monkeypatch.setattr(config, "SET_ASIDE_STRICT_EXTRA", True)
    report = _sa("SDVOSB", "FAR 52.219-27 plus extra 52.219-6 rep")
    assert report.overall_severity == "warn"
    assert report.mismatches[0].extra == ["52.219-6"]


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [("8A", "8(a)"), ("HUBZONE", "HUBZone"), ("SMALL_BUSINESS", "total_small_business")],
)
def test_set_aside_wizard_aliases(alias, canonical):
    report = _sa(alias, "")
    assert report.mismatches[0].set_aside == canonical


def test_full_and_open_and_unknown_are_info():
    assert _sa("FULL_AND_OPEN", "anything").overall_severity == "info"
    assert _sa(None, "anything").overall_severity == "info"
    assert _sa("MARTIAN", "anything").overall_severity == "info"


# ---------------------------------------------------------------------------
# check_clin_coverage (programmatic — table-driven)
# ---------------------------------------------------------------------------


def _clin(b, c, f, l):  # noqa: E741 — section letter
    return check_clin_coverage.func(  # type: ignore[attr-defined]
        section_b=b, section_c=c, section_f=f, section_l=l
    )


_SECTION_B = "0001  Cloud managed services  EA 12\nCLIN 0002 Optional surge support"


def test_clin_all_aligned_info():
    report = _clin(
        _SECTION_B,
        "C.2 Task per CLIN 0001 and CLIN 0002",
        "F.1 deliveries for 0001 and 0002",
        "L.5 price 0001 and 0002 separately",
    )
    assert report.overall_severity == "info"
    assert report.gaps == []


def test_clin_missing_one_section_warn():
    report = _clin(
        _SECTION_B,
        "C.2 covers CLIN 0001 and CLIN 0002",
        "F.1 deliveries for 0001 only",
        "L.5 price 0001 and 0002",
    )
    assert report.overall_severity == "warn"
    gap = report.gaps[0]
    assert gap.clin_id == "0002"
    assert gap.missing_in == ["F"]
    assert gap.severity == "warn"


def test_clin_missing_two_sections_fail_at_gap_level_warn_overall():
    """Gap-level fidelity preserved; Phase 1 clamps the OVERALL to warn."""
    report = _clin(
        _SECTION_B,
        "C.2 covers CLIN 0001 only",
        "F.1 deliveries for 0001 only",
        "L.5 price 0001 and 0002",
    )
    gap = next(g for g in report.gaps if g.clin_id == "0002")
    assert gap.severity == "fail"
    assert set(gap.missing_in) == {"C", "F"}
    assert report.overall_severity == "warn"  # ADR-0013 D5 clamp


def test_clin_section_b_none_is_info_skip_marker():
    """ADR-0015 critic-pass fix — distinguish 'no issues' from 'couldn't check'."""
    report = _clin(None, "C text", "F text", "L text")
    assert report.overall_severity == "info"
    assert report.gaps[0].clin_id == "<n/a>"


def test_clin_no_clins_in_b_is_clean_info():
    report = _clin("narrative pricing, no CLIN table", "C", "F", "L")
    assert report.overall_severity == "info"
    assert report.gaps == []
