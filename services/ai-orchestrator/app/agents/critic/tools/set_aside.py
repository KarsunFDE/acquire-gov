"""``check_set_aside_consistency`` — programmatic critic tool (design ref §18.5).

Validates Section K reps + certs against the Section A set-aside designation
via a static FAR-prescription table. ``SET_ASIDE_STRICT_EXTRA`` (config)
controls whether clauses beyond the requirement raise warn (False in Phase 1
— extras are info-only, avoiding false positives while CO templates
legitimately over-include).
"""
from __future__ import annotations

import re

from langchain.tools import tool

from app import config
from app.agents.schemas import SetAsideConsistencyReport, SetAsideMismatch

SET_ASIDE_REQUIRED_CLAUSES: dict[str, frozenset[str]] = {
    "8(a)": frozenset({"52.219-18"}),
    "SDVOSB": frozenset({"52.219-27"}),
    "WOSB": frozenset({"52.219-30"}),
    "HUBZone": frozenset({"52.219-3"}),
    "total_small_business": frozenset({"52.219-6"}),
}

# Wizard-enum → FAR spelling (matches clause_applicability.json _meta).
_ALIASES: dict[str, str | None] = {
    "8A": "8(a)",
    "HUBZONE": "HUBZone",
    "SMALL_BUSINESS": "total_small_business",
    "FULL_AND_OPEN": None,
}

# FAR clause citation, e.g. 52.219-27 (with optional Alternate suffix ignored).
_CLAUSE_RE = re.compile(r"\b52\.\d{3}-\d+\b")


def _extract_far_clauses_from_section_k(section_k_text: str) -> set[str]:
    return set(_CLAUSE_RE.findall(section_k_text))


@tool
def check_set_aside_consistency(
    set_aside: str | None, section_k_text: str | None
) -> SetAsideConsistencyReport:
    """Validate Section K representations match the Section A set-aside
    designation (e.g., SDVOSB requires FAR 52.219-27 in Section K).

    Call this exactly once with the solicitation's set_aside and Section K text.
    """
    canonical = _ALIASES.get(set_aside, set_aside) if set_aside else None
    if not canonical or canonical not in SET_ASIDE_REQUIRED_CLAUSES:
        return SetAsideConsistencyReport(mismatches=[], overall_severity="info")
    required = SET_ASIDE_REQUIRED_CLAUSES[canonical]
    actual = _extract_far_clauses_from_section_k(section_k_text or "")
    missing = sorted(required - actual)
    extra = sorted(actual - required) if config.SET_ASIDE_STRICT_EXTRA else []
    sev = "warn" if (missing or extra) else "info"
    return SetAsideConsistencyReport(
        mismatches=[
            SetAsideMismatch(
                set_aside=canonical,
                expected_reps=sorted(required),
                actual_reps=sorted(actual),
                missing=missing,
                extra=extra,
                severity=sev,
            )
        ],
        overall_severity=sev,
    )
