"""Preflight input-validation gate (ADR-0015; design ref §19).

Programmatic stage between ``QueryGuardrails`` and agent construction.
Two-tier policy:
- hard-required fields missing → handler returns 422, no agent runs, no spend;
- soft-required fields missing → run proceeds, ``degraded_context`` flags the
  response + audit row so the CO sees the retrieval-quality caveat.

Batch preflight lives here too (used by /batch in Phase 3) — keeps the policy
collocated per phase-1 spec §7 P1.1.
"""
from __future__ import annotations

from app.agents.schemas import BatchDraftRequest, DraftSectionRequest, PreflightResult

# Tier tables per ADR-0015 D3 (design ref §19.2).
HARD_REQUIRED_SINGLE = ["solicitation_id", "section_id", "contract_type"]
# Extra hard fields when drafting content-bearing sections (C = SOW, H = special reqs).
HARD_REQUIRED_SINGLE_CONTENT_SECTIONS = ["naics", "set_aside"]
SOFT_REQUIRED_SINGLE = ["agency_supplement"]
HARD_REQUIRED_BATCH = [
    "solicitation_id", "naics", "set_aside", "contract_type", "agency_supplement",
]


def _is_empty(v: object) -> bool:
    return v in (None, "")


def preflight_single_section(
    request: DraftSectionRequest, tenant_id: str | None
) -> PreflightResult:
    """Tier-validate a single-section draft request (ADR-0015 D2)."""
    missing = [f for f in HARD_REQUIRED_SINGLE if _is_empty(getattr(request, f, None))]
    if request.section_id in {"C", "H"}:
        missing += [
            f for f in HARD_REQUIRED_SINGLE_CONTENT_SECTIONS
            if _is_empty(getattr(request, f, None))
        ]
    if _is_empty(tenant_id):
        missing.append("tenant_id")  # belt-and-suspenders; ADR-0008 D2 enforces at factory
    degraded = [f for f in SOFT_REQUIRED_SINGLE if _is_empty(getattr(request, f, None))]
    # naics/set_aside are soft for K/L/M (hard only for C/H above).
    if request.section_id in {"K", "L", "M"}:
        degraded += [
            f for f in HARD_REQUIRED_SINGLE_CONTENT_SECTIONS
            if _is_empty(getattr(request, f, None))
        ]
    return PreflightResult(
        ready=not missing, missing_required=missing, degraded_context=degraded
    )


def preflight_batch(request: BatchDraftRequest, tenant_id: str | None) -> PreflightResult:
    """Tier-validate a batch draft request — all Step 1 metadata is hard (D2)."""
    missing = [f for f in HARD_REQUIRED_BATCH if _is_empty(getattr(request, f, None))]
    if not request.provenances or all(
        v is not None for v in request.provenances.values()
    ):
        missing.append("at_least_one_null_provenance")
    if _is_empty(tenant_id):
        missing.append("tenant_id")
    return PreflightResult(ready=not missing, missing_required=missing, degraded_context=[])
