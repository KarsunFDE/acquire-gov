"""Generate the M1 critic-metric fixture set (design ref §18.8).

Deterministic synthetic solicitations: 20 with known mismatches injected
(8 set-aside, 6 CLIN, 6 L↔M) + 20 known-good. Output:
``eval/fixtures/m1_critic_fixtures.jsonl``.

Run: ``python -m eval.build_m1_fixtures`` (from services/ai-orchestrator).
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).parent / "fixtures" / "m1_critic_fixtures.jsonl"

_SET_ASIDES = {
    "8(a)": "52.219-18",
    "SDVOSB": "52.219-27",
    "WOSB": "52.219-30",
    "HUBZone": "52.219-3",
    "total_small_business": "52.219-6",
}

_L_GOOD = (
    "L.1 GENERAL. Submit via SAM.gov.\n"
    "L.5.1 Volume I — Technical Approach (40 pages) priced per CLIN 0001 and 0002.\n"
    "L.5.2 Volume II — Past Performance questionnaire.\n"
    "L.5.3 Volume III — Price per CLIN 0001 and 0002."
)
_M_GOOD = (
    "M.1 Best-value tradeoff per FAR 15.101-1.\n"
    "M.3.1 Technical Approach (45%).\n"
    "M.3.2 Past Performance (30%).\n"
    "M.3.3 Price (25%)."
)
_M_MISALIGNED = (
    "M.1 Best-value tradeoff per FAR 15.101-1.\n"
    "M.3.1 Technical Approach (40%).\n"
    "M.3.2 Small Disadvantaged Business Participation (35%).\n"  # no L instruction
    "M.3.3 Price (25%)."
)
_B = "0001 Cloud managed services — base year  EA 12\nCLIN 0002 Optional surge support"
_C_GOOD = "C.1 SCOPE per CLIN 0001.\nC.2 Surge tasks per CLIN 0002."
_F_GOOD = "F.1 Monthly deliveries for 0001.\nF.2 Surge deliveries for 0002 within 30 days."
_C_GAP = "C.1 SCOPE per CLIN 0001 only."          # 0002 missing in C
_F_GAP = "F.1 Monthly deliveries for 0001 only."  # 0002 missing in F


def _k_with(clause: str) -> str:
    return f"K.1 52.204-7 SAM.\nK.2 FAR {clause} incorporated by reference."


def _fixture(i: int, kind: str, set_aside: str, clause: str) -> dict:
    if kind == "set_aside_mismatch":
        sections = {"B": _B, "C": _C_GOOD, "F": _F_GOOD,
                    "K": "K.1 52.204-7 SAM only.",  # required rep missing
                    "L": _L_GOOD, "M": _M_GOOD}
    elif kind == "clin_gap":
        sections = {"B": _B, "C": _C_GAP, "F": _F_GAP,
                    "K": _k_with(clause), "L": _L_GOOD, "M": _M_GOOD}
    elif kind == "lm_mismatch":
        sections = {"B": _B, "C": _C_GOOD, "F": _F_GOOD,
                    "K": _k_with(clause), "L": _L_GOOD, "M": _M_MISALIGNED}
    else:  # known_good
        sections = {"B": _B, "C": _C_GOOD, "F": _F_GOOD,
                    "K": _k_with(clause), "L": _L_GOOD, "M": _M_GOOD}
    return {
        "fixture_id": f"fx-{i:03d}",
        "kind": kind,
        "set_aside": set_aside,
        "sections": sections,
    }


def build() -> list[dict]:
    fixtures: list[dict] = []
    set_asides = list(_SET_ASIDES.items())
    i = 1
    # 8 set-aside mismatches (cycle the 5 set-asides)
    for n in range(8):
        sa, clause = set_asides[n % len(set_asides)]
        fixtures.append(_fixture(i, "set_aside_mismatch", sa, clause)); i += 1
    # 6 CLIN gaps
    for n in range(6):
        sa, clause = set_asides[n % len(set_asides)]
        fixtures.append(_fixture(i, "clin_gap", sa, clause)); i += 1
    # 6 L↔M mismatches
    for n in range(6):
        sa, clause = set_asides[n % len(set_asides)]
        fixtures.append(_fixture(i, "lm_mismatch", sa, clause)); i += 1
    # 20 known-good
    for n in range(20):
        sa, clause = set_asides[n % len(set_asides)]
        fixtures.append(_fixture(i, "known_good", sa, clause)); i += 1
    return fixtures


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for row in build():
            f.write(json.dumps(row) + "\n")
    print(f"wrote {OUT} ({len(build())} fixtures)")


if __name__ == "__main__":
    main()
