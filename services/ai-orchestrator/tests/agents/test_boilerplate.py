"""DEMO-REDESIGN-spec §2 — boilerplate (D-G/K) + stub-bundle behavior.

No Bedrock: D-G uses the template path (AI_STUB_MODE), K is fully programmatic.
Locks the set-aside → clause mapping and the full stub-bundle shape that the
demo depends on.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import config
from app.agents import boilerplate as bp


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setattr(config, "AI_STUB_MODE", True)


def test_defg_generates_all_four_as_final_sections():
    out = bp.generate_defg({"title": "Cloud BPA", "naics": "541512"})
    assert set(out) == {"D", "E", "F", "G"}
    for sid, final in out.items():
        assert final.outcome == "draft_returned"
        assert final.section_text
        assert final.gate_decision == "pass"
        assert final.requires_human_review is False


def test_section_k_small_business_pairs_limitations_clause():
    k = bp.generate_section_k("SMALL_BUSINESS")
    clauses = {c.far_clause for c in k.citations}
    assert {"52.204-8", "52.219-1", "52.219-6", "52.219-14"} <= clauses


def test_section_k_sdvosb_uses_correct_notice_clause():
    k = bp.generate_section_k("SDVOSB")
    clauses = {c.far_clause for c in k.citations}
    assert "52.219-27" in clauses          # SDVOSB notice
    assert "52.219-14" in clauses          # small-biz limitations always paired


def test_section_k_full_and_open_has_no_set_aside_notice():
    k = bp.generate_section_k("FULL_AND_OPEN")
    clauses = {c.far_clause for c in k.citations}
    assert clauses == {"52.204-8", "52.219-1"}   # base reps only
    assert "52.219-14" not in clauses


def test_stub_bundle_populates_all_drafted_sections():
    from app.stub_drafts import stub_bundle

    body = SimpleNamespace(
        solicitation_id="Cloud Managed Services BPA", naics="541512",
        set_aside="SDVOSB", contract_type="FFP", agency_supplement="GSAM",
        eval_approach="LPTA", period_of_performance="12mo+4",
        place_of_performance="DC hybrid", provenances={}, part_iii_attachments=[],
    )
    bundle = stub_bundle(body, request_id="r", batch_run_id="b")
    assert bundle.overall_outcome == "batch_completed"
    assert set(bundle.parts) == {"I", "II", "III", "IV"}
    assert set(bundle.parts["I"].sections) == {"C", "D", "E", "F", "G", "H"}
    assert set(bundle.parts["IV"].sections) == {"K", "L", "M"}
    # eval_approach threads through to Section M.
    assert "LPTA" in (bundle.parts["IV"].sections["M"].section_text or "")
    # consistency report present and non-blocking.
    assert bundle.consistency_report.blocks_submit is False


def test_stub_bundle_respects_human_owned_sections():
    from app.stub_drafts import stub_bundle

    body = SimpleNamespace(
        solicitation_id="sol", naics="x", set_aside="WOSB", contract_type="FFP",
        agency_supplement=None, eval_approach="TRADEOFF",
        period_of_performance=None, place_of_performance=None,
        provenances={"C": "human", "D": "human"}, part_iii_attachments=[],
    )
    bundle = stub_bundle(body, request_id="r", batch_run_id="b")
    # C and D were human-owned → not regenerated.
    assert "C" not in bundle.parts["I"].sections
    assert "D" not in bundle.parts["I"].sections
    assert {"E", "F", "G", "H"} <= set(bundle.parts["I"].sections)
