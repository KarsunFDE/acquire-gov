"""P3.3 — resolve_part_ii_clauses table-driven tests (ADR-0014 D3)."""
from __future__ import annotations

import pytest

from app.agents.coordinator.part_ii import resolve_part_ii_clauses


def _citations(set_aside=None, contract_type=None, agency_supplement=None) -> set[str]:
    result = resolve_part_ii_clauses(
        set_aside=set_aside,
        contract_type=contract_type,
        agency_supplement=agency_supplement,
    )
    return {c.citation for c in result.clauses_by_reference}


BASE = {"52.212-4", "52.204-7", "52.204-21", "52.215-1", "52.233-1"}


@pytest.mark.parametrize(
    ("set_aside", "expected_clause"),
    [
        ("8(a)", "52.219-18"),
        ("8A", "52.219-18"),               # wizard-enum alias
        ("SDVOSB", "52.219-27"),
        ("WOSB", "52.219-30"),
        ("HUBZone", "52.219-3"),
        ("HUBZONE", "52.219-3"),           # wizard-enum alias
        ("total_small_business", "52.219-6"),
        ("SMALL_BUSINESS", "52.219-6"),    # wizard-enum alias
    ],
)
def test_set_aside_clauses(set_aside, expected_clause):
    cites = _citations(set_aside=set_aside, contract_type="FFP")
    assert expected_clause in cites
    assert "52.219-14" in cites  # limitations on subcontracting rides every set-aside
    assert BASE <= cites


@pytest.mark.parametrize(
    ("contract_type", "expected_clause"),
    [
        ("FFP", "52.232-1"),
        ("FFP", "52.249-1"),
        ("CPFF", "52.216-8"),
        ("CPFF", "52.232-20"),
        ("T_AND_M", "52.232-7"),
        ("IDIQ", "52.216-22"),
        ("BPA", "52.216-18"),
    ],
)
def test_contract_type_clauses(contract_type, expected_clause):
    cites = _citations(set_aside="SDVOSB", contract_type=contract_type)
    assert expected_clause in cites


def test_full_and_open_maps_to_no_set_aside_clauses():
    cites = _citations(set_aside="FULL_AND_OPEN", contract_type="FFP")
    assert not any(c.startswith("52.219") for c in cites)
    assert BASE <= cites


def test_agency_supplement_rows():
    assert "552.212-4" in _citations(
        set_aside="SDVOSB", contract_type="FFP", agency_supplement="GSAM"
    )
    assert "252.204-7012" in _citations(
        set_aside="SDVOSB", contract_type="FFP", agency_supplement="DFARS"
    )


def test_unknown_combination_resolves_empty_not_500():
    result = resolve_part_ii_clauses(
        set_aside="MARTIAN_VENDORS", contract_type="BARTER", agency_supplement="MOONFAR"
    )
    # Base clauses still resolve; unknown keys contribute nothing; echo intact.
    assert {c.citation for c in result.clauses_by_reference} == BASE
    assert result.resolved_for == {
        "set_aside": "MARTIAN_VENDORS",
        "contract_type": "BARTER",
        "agency_supplement": "MOONFAR",
    }


def test_deterministic_and_sorted():
    a = resolve_part_ii_clauses(set_aside="SDVOSB", contract_type="FFP", agency_supplement="GSAM")
    b = resolve_part_ii_clauses(set_aside="SDVOSB", contract_type="FFP", agency_supplement="GSAM")
    assert a == b
    cites = [c.citation for c in a.clauses_by_reference]
    assert cites == sorted(cites)
    assert a.source == "far_snapshot_index"
