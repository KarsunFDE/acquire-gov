"""Part II (Section I) programmatic clause resolution (ADR-0014 D3).

No LLM, no agent — a deterministic lookup over the FAR clause-applicability
matrix asset (``docs/reference/far/clause_applicability.json``). Unknown
combinations resolve to an empty list with an explicit ``resolved_for`` echo,
never a 500.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.agents.schemas import FARClauseReference, PartIIClauseList

log = logging.getLogger("ai-orchestrator.coordinator.part_ii")


def _matrix_path() -> Path:
    """Resolve the clause-applicability matrix.

    ``CLAUSE_MATRIX_PATH`` wins (the container mounts docs/reference/far
    read-only and sets it); dev fallback climbs to the repo root —
    app/agents/coordinator/part_ii.py → parents[5].
    """
    env_path = os.environ.get("CLAUSE_MATRIX_PATH")
    if env_path:
        return Path(env_path)
    resolved = Path(__file__).resolve()
    if len(resolved.parents) > 5:
        candidate = (
            resolved.parents[5]
            / "docs" / "reference" / "far" / "clause_applicability.json"
        )
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "clause_applicability.json not found — set CLAUSE_MATRIX_PATH"
    )


@lru_cache(maxsize=1)
def _load_matrix() -> dict:
    with _matrix_path().open(encoding="utf-8") as f:
        return json.load(f)


def _canonical_set_aside(matrix: dict, set_aside: str | None) -> str | None:
    """Map wizard enum spellings (8A, HUBZONE, SMALL_BUSINESS, ...) to the
    FAR spellings the matrix keys on; None for full-and-open."""
    if set_aside is None:
        return None
    aliases = matrix.get("_meta", {}).get("set_aside_aliases", {})
    if set_aside in aliases:
        return aliases[set_aside]
    return set_aside


def resolve_part_ii_clauses(
    *,
    set_aside: str | None,
    contract_type: str | None,
    agency_supplement: str | None,
) -> PartIIClauseList:
    """Deterministic Section I clause list for the given Step 1 triple."""
    matrix = _load_matrix()
    snapshot = date.fromisoformat(
        matrix.get("_meta", {}).get("snapshot_date", "1970-01-01")
    )

    refs: list[FARClauseReference] = []
    seen: set[str] = set()

    def _extend(rows: list[dict]) -> None:
        for row in rows:
            if row["citation"] in seen:
                continue
            seen.add(row["citation"])
            refs.append(FARClauseReference(**row))

    _extend(matrix.get("base", []))

    canonical_sa = _canonical_set_aside(matrix, set_aside)
    if canonical_sa:
        rows = matrix.get("set_aside", {}).get(canonical_sa)
        if rows is None:
            log.warning("unknown set_aside %r — no set-aside clauses resolved", set_aside)
        else:
            _extend(rows)

    if contract_type:
        rows = matrix.get("contract_type", {}).get(contract_type)
        if rows is None:
            log.warning("unknown contract_type %r — no type clauses resolved", contract_type)
        else:
            _extend(rows)

    if agency_supplement:
        rows = matrix.get("agency_supplement", {}).get(agency_supplement)
        if rows is None:
            log.warning("unknown agency_supplement %r — no supplement clauses", agency_supplement)
        else:
            _extend(rows)

    return PartIIClauseList(
        clauses_by_reference=sorted(refs, key=lambda r: r.citation),
        source="far_snapshot_index",
        snapshot_date=snapshot,
        resolved_for={
            "set_aside": set_aside,
            "contract_type": contract_type,
            "agency_supplement": agency_supplement,
        },
    )
