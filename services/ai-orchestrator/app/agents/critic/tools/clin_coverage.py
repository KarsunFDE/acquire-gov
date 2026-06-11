"""``check_clin_coverage`` — programmatic critic tool (design ref §18.5).

Extracts CLIN identifiers from Section B and checks each appears in Section C
(SOW), Section F (delivery schedule), and Section L (pricing instruction).

Gap-level severity is preserved faithfully (warn for 1 missing section, fail
for 2+) so Phase 1.5 can flip the aggregation clamp without re-running the
tool; Phase 1 clamps the OVERALL severity to warn at most (ADR-0013 D5).

``section_b is None`` returns an info-severity skip marker (not silently-empty
gaps) so the wizard's Step 12 surface can distinguish "no CLIN issues" from
"couldn't check" (ADR-0015 critic-pass minor fix).
"""
from __future__ import annotations

import re
from typing import Literal

from langchain.tools import tool

from app.agents.schemas import CLINCoverageReport, CLINGap

# CLIN id: 4 digits (optionally followed by 2-char SubCLIN suffix) near "CLIN"
# or at a line start in Section B's pricing table.
_CLIN_NEAR_RE = re.compile(r"\bCLIN\s*(\d{4})\b", re.IGNORECASE)
_CLIN_LINE_RE = re.compile(r"^\s*(\d{4})\b", re.MULTILINE)


def _extract_clins(section_b: str) -> list[str]:
    found = set(_CLIN_NEAR_RE.findall(section_b)) | set(_CLIN_LINE_RE.findall(section_b))
    return sorted(found)


def _references_clin(section_text: str | None, clin: str) -> bool:
    if not section_text:
        return False
    return clin in section_text


@tool
def check_clin_coverage(
    section_b: str | None,
    section_c: str | None,
    section_f: str | None,
    section_l: str | None,
) -> CLINCoverageReport:
    """Cross-section CLIN reference check (Section B ↔ C ↔ F ↔ L): every CLIN
    priced in Section B should be referenced in the SOW, the delivery
    schedule, and the pricing instructions.

    Call this exactly once with the four section texts (null when missing).
    """
    if section_b is None:
        return CLINCoverageReport(
            gaps=[CLINGap(clin_id="<n/a>", missing_in=[], severity="info")],
            overall_severity="info",
        )
    clins = _extract_clins(section_b)
    gaps: list[CLINGap] = []
    for clin in clins:
        missing_in: list[Literal["C", "F", "L"]] = []
        if not _references_clin(section_c, clin):
            missing_in.append("C")
        if not _references_clin(section_f, clin):
            missing_in.append("F")
        if not _references_clin(section_l, clin):
            missing_in.append("L")
        if missing_in:
            sev = "warn" if len(missing_in) == 1 else "fail"
            gaps.append(CLINGap(clin_id=clin, missing_in=missing_in, severity=sev))
    if not gaps:
        return CLINCoverageReport(gaps=[], overall_severity="info")
    # ADR-0013 D5 Phase 1 clamp: aggregation never exceeds warn even if a
    # gap-level row is fail.
    return CLINCoverageReport(gaps=gaps, overall_severity="warn")
