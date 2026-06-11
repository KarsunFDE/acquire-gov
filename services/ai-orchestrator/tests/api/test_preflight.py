"""P1.1 — preflight tier-policy unit tests (ADR-0015 D2/D3).

Handler-level 422/200 behavior is covered in test_draft_section_endpoint.py;
these tests pin the pure-function policy table.
"""
from __future__ import annotations

import pytest

from app.agents.schemas import BatchDraftRequest, DraftSectionRequest
from app.api.preflight import preflight_batch, preflight_single_section


def _req(**over) -> DraftSectionRequest:
    base = dict(
        section_id="C",
        solicitation_id="sol-1",
        naics="541512",
        set_aside="SDVOSB",
        contract_type="FFP",
        agency_supplement="GSAM",
    )
    base.update(over)
    return DraftSectionRequest(**base)


def test_all_hard_present_ready():
    pf = preflight_single_section(_req(), "tenant_A")
    assert pf.ready is True
    assert pf.missing_required == []
    assert pf.degraded_context == []


@pytest.mark.parametrize("section_id", ["C", "H"])
def test_content_sections_require_naics_and_set_aside(section_id: str):
    pf = preflight_single_section(
        _req(section_id=section_id, naics=None, set_aside=None), "tenant_A"
    )
    assert pf.ready is False
    assert "naics" in pf.missing_required
    assert "set_aside" in pf.missing_required


@pytest.mark.parametrize("section_id", ["K", "L", "M"])
def test_naics_set_aside_soft_for_klm(section_id: str):
    pf = preflight_single_section(
        _req(section_id=section_id, naics=None, set_aside=None), "tenant_A"
    )
    assert pf.ready is True
    assert "naics" in pf.degraded_context
    assert "set_aside" in pf.degraded_context


def test_contract_type_hard_for_all_sections():
    for section_id in ["A", "C", "L"]:
        pf = preflight_single_section(
            _req(section_id=section_id, contract_type=None), "tenant_A"
        )
        assert pf.ready is False
        assert "contract_type" in pf.missing_required


def test_agency_supplement_always_soft():
    pf = preflight_single_section(_req(agency_supplement=None), "tenant_A")
    assert pf.ready is True
    assert pf.degraded_context == ["agency_supplement"]


def test_missing_tenant_id_hard():
    pf = preflight_single_section(_req(), None)
    assert pf.ready is False
    assert "tenant_id" in pf.missing_required
    pf2 = preflight_single_section(_req(), "")
    assert "tenant_id" in pf2.missing_required


def test_empty_string_treated_as_missing():
    pf = preflight_single_section(_req(naics=""), "tenant_A")
    assert pf.ready is False
    assert "naics" in pf.missing_required


# ---------------------------------------------------------------------------
# Batch preflight (consumed by /batch in Phase 3)
# ---------------------------------------------------------------------------


def _batch(**over) -> BatchDraftRequest:
    base = dict(
        solicitation_id="sol-1",
        naics="541512",
        set_aside="SDVOSB",
        contract_type="FFP",
        agency_supplement="GSAM",
        provenances={"C": None, "H": None, "L": None, "M": None},
    )
    base.update(over)
    return BatchDraftRequest(**base)


def test_batch_all_present_ready():
    pf = preflight_batch(_batch(), "tenant_A")
    assert pf.ready is True


def test_batch_full_step1_hard():
    pf = preflight_batch(_batch(agency_supplement=None, contract_type=None), "tenant_A")
    assert pf.ready is False
    assert "agency_supplement" in pf.missing_required
    assert "contract_type" in pf.missing_required


def test_batch_requires_at_least_one_null_provenance():
    pf = preflight_batch(
        _batch(provenances={"C": "human", "H": "ai-edited"}), "tenant_A"
    )
    assert pf.ready is False
    assert "at_least_one_null_provenance" in pf.missing_required


def test_batch_empty_provenances_rejected():
    pf = preflight_batch(_batch(provenances={}), "tenant_A")
    assert pf.ready is False
    assert "at_least_one_null_provenance" in pf.missing_required
