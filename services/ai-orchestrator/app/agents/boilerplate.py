"""Boilerplate section generator — FAR UCF Sections D, E, F, G, K.

DEMO-REDESIGN-spec §2. These sections are near-verbatim FAR/GSAR clause text
plus a few solicitation specifics (period/place of performance, set-aside), so
they do NOT need the full retrieval+agent drafting pipeline:

- **D/E/F/G** — one ``with_structured_output`` Haiku call that merges the
  canonical clause language (anchored by the few-shot snippets in
  ``docs/reference/solicitation-fewshot.md``) with the run's specifics. A single
  call has **zero recursion surface** — no agent, no tools, cannot loop
  (DEMO-REDESIGN-spec §1).
- **K** — fully programmatic. Reps/certs are incorporation-by-reference
  (FAR 52.204-8 → SAM.gov) plus the ONE set-aside notice clause; no free
  generation, no LLM. Reuses the Part II clause-matrix selection pattern.

Both paths emit ``FinalDraftSection`` (outcome=draft_returned, gate=pass,
requires_human_review=False) so the coordinator and frontend treat boilerplate
exactly like agent-drafted sections. ``AI_STUB_MODE`` (or any Bedrock failure)
falls back to the filled template verbatim — the demo works with no key.
"""
from __future__ import annotations

import logging
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.agents.schemas import Citation, FinalDraftSection

log = logging.getLogger("ai-orchestrator.boilerplate")

# Sections this module owns.
DEFG_SECTIONS = ("D", "E", "F", "G")


# --------------------------------------------------------------------------
# Canonical templates (sourced — docs/reference/solicitation-fewshot.md).
# Placeholders are filled from the run context; this filled text is BOTH the
# stub output and the few-shot anchor handed to Haiku on the live path.
# --------------------------------------------------------------------------

_DEFG_TEMPLATES: dict[str, str] = {
    "D": (
        "D.1 PACKAGING AND MARKING\n"
        "Unless otherwise specified, all items shall be preserved, packaged, and "
        "packed in accordance with normal commercial practices and the Uniform "
        "Freight Classification and National Motor Freight Classification in "
        "effect at time of shipment. All deliverables shall be marked with the "
        "contract number, line item, and consignee for the {title} requirement.\n"
        "(Ref: GSAR 552.211-75, Preservation, Packaging, and Packing.)"
    ),
    "E": (
        "E.1 INSPECTION AND ACCEPTANCE\n"
        "Inspection and acceptance of all supplies and services under this "
        "contract shall be performed in accordance with FAR 52.246-2, Inspection "
        "of Supplies—Fixed-Price. The Contractor shall tender to the Government "
        "for acceptance only supplies and services that conform to contract "
        "requirements. Final acceptance shall be conclusive except as regards "
        "latent defects, fraud, or gross mistakes amounting to fraud."
    ),
    "F": (
        "F.1 DELIVERIES OR PERFORMANCE\n"
        "The period of performance is {period_of_performance}, unless extended in "
        "accordance with FAR 52.217-9, Option to Extend the Term of the Contract. "
        "Place of performance is {place_of_performance}. Delivery shall be F.o.b. "
        "Destination per FAR 52.247-34; the Contractor is responsible for any loss "
        "or damage to goods occurring before receipt at the delivery point."
    ),
    "G": (
        "G.1 CONTRACT ADMINISTRATION DATA\n"
        "Invoices shall be submitted to the designated billing office and must "
        "constitute a proper invoice under FAR 52.232-25, Prompt Payment, "
        "including all elements of paragraph (a)(3). Improper invoices will be "
        "returned within seven (7) days with the reasons stated. The Contracting "
        "Officer's Representative (COR) will be designated at award."
    ),
}

# Section K — set-aside → notice clause(s). Base reps always present; any
# small-business set-aside additionally carries 52.219-14. (Sourced table:
# docs/reference/solicitation-fewshot.md.)
_K_BASE = [
    ("52.204-8", "Annual Representations and Certifications"),
    ("52.219-1", "Small Business Program Representations"),
]
_K_SET_ASIDE: dict[str, list[tuple[str, str]]] = {
    "SMALL_BUSINESS": [("52.219-6", "Notice of Total Small Business Set-Aside")],
    "8A": [("52.219-18", "Notification of Competition Limited to Eligible 8(a) Participants")],
    "HUBZONE": [
        ("52.219-3", "Notice of HUBZone Set-Aside or Sole-Source Award"),
        ("52.219-4", "Notice of Price Evaluation Preference for HUBZone Small Business Concerns"),
    ],
    "SDVOSB": [("52.219-27", "Notice of Set-Aside for Service-Disabled Veteran-Owned Small Business Concerns")],
    "WOSB": [("52.219-30", "Notice of Set-Aside for Women-Owned Small Business Concerns")],
}
# Set-asides that are small-business programs → always pair 52.219-14.
_SMALL_BIZ_SET_ASIDES = {"SMALL_BUSINESS", "8A", "HUBZONE", "SDVOSB", "WOSB"}
_K_LIMITATIONS = ("52.219-14", "Limitations on Subcontracting")


class _DEFGPayload(BaseModel):
    """Structured output for the single Haiku D-E-F-G call."""

    model_config = ConfigDict(extra="forbid")

    d: str = Field(min_length=1)
    e: str = Field(min_length=1)
    f: str = Field(min_length=1)
    g: str = Field(min_length=1)


def _boilerplate_chat():
    """Factory — tests monkeypatch this."""
    from app.agents.model_factory import build_chat  # noqa: PLC0415 — lazy

    return build_chat(
        config.BEDROCK_BOILERPLATE_MODEL,
        max_tokens=config.BEDROCK_BOILERPLATE_MAX_TOKENS,
    )


def _fill(template: str, ctx: dict) -> str:
    return template.format(
        title=ctx.get("title") or "this acquisition",
        period_of_performance=ctx.get("period_of_performance") or "a 12-month base period with up to four 12-month option periods",
        place_of_performance=ctx.get("place_of_performance") or "the place(s) specified in the order",
    )


def _final(section_id: str, text: str, citations: list[Citation]) -> FinalDraftSection:
    return FinalDraftSection(
        outcome="draft_returned",
        section_text=text,
        section_id=section_id,  # type: ignore[arg-type]
        citations=citations,
        gate_decision="pass",
        requires_human_review=False,
        rerank_top_score=None,
        request_id="",  # handler stamps authoritative ids
        run_id="",
    )


def _clause_citation(citation: str, title: str, far_part: str) -> Citation:
    return Citation(
        chunk_id=f"template:{citation}",
        far_part=far_part,
        far_section=citation,
        far_clause=citation,
        snapshot_date=date.today(),
        relevance_score=1.0,
        text=f"FAR {citation} — {title} (incorporated by reference).",
    )


_DEFG_CITES = {
    "D": [("552.211-75", "Preservation, Packaging, and Packing", "GSAR")],
    "E": [("52.246-2", "Inspection of Supplies—Fixed-Price", "46")],
    "F": [("52.247-34", "F.o.b. Destination", "47"), ("52.217-9", "Option to Extend the Term of the Contract", "17")],
    "G": [("52.232-25", "Prompt Payment", "32")],
}


def _defg_citations(sid: str) -> list[Citation]:
    return [_clause_citation(c, t, p) for c, t, p in _DEFG_CITES[sid]]


def generate_defg(ctx: dict) -> dict[str, FinalDraftSection]:
    """Generate Sections D, E, F, G in one bounded call.

    Stub mode (or any Bedrock error) → filled canonical templates. Live →
    single Haiku ``with_structured_output`` call that polishes the templates
    with the run's specifics. Either way: one call, no loop.
    """
    filled = {sid: _fill(_DEFG_TEMPLATES[sid], ctx) for sid in DEFG_SECTIONS}

    if not config.AI_STUB_MODE:
        try:
            filled = _polish_defg(filled, ctx)
        except Exception as exc:  # noqa: BLE001 — never fail the draft on boilerplate
            log.warning("D-G Haiku polish failed (%s); using templates verbatim", exc)

    return {
        sid: _final(sid, filled[sid], _defg_citations(sid))
        for sid in DEFG_SECTIONS
    }


def _polish_defg(filled: dict[str, str], ctx: dict) -> dict[str, str]:
    """One Haiku structured call. Bounded by max_tokens; no agent, no tools."""
    chat = _boilerplate_chat().with_structured_output(_DEFGPayload, include_raw=True)
    prompt = (
        "You are completing the boilerplate sections of a federal solicitation "
        "in the FAR Uniform Contract Format. Lightly adapt each template below to "
        "the acquisition specifics — do NOT add requirements not present in the "
        "template; keep the FAR/GSAR clause references intact; keep each section "
        "concise (a short paragraph).\n\n"
        f"Acquisition: {ctx.get('title') or '(untitled)'} | NAICS {ctx.get('naics') or 'n/a'} | "
        f"set-aside {ctx.get('set_aside') or 'full and open'} | "
        f"contract type {ctx.get('contract_type') or 'n/a'}\n"
        f"Period of performance: {ctx.get('period_of_performance') or 'n/a'}\n"
        f"Place of performance: {ctx.get('place_of_performance') or 'n/a'}\n\n"
        "=== TEMPLATE D ===\n" + filled["D"] + "\n\n"
        "=== TEMPLATE E ===\n" + filled["E"] + "\n\n"
        "=== TEMPLATE F ===\n" + filled["F"] + "\n\n"
        "=== TEMPLATE G ===\n" + filled["G"] + "\n\n"
        "Return adapted text for each of d, e, f, g."
    )
    result = chat.invoke(prompt)
    parsed: _DEFGPayload | None = result.get("parsed")
    if parsed is None:
        raise ValueError(f"defg_parse_failed: {result.get('parsing_error')}")
    return {"D": parsed.d, "E": parsed.e, "F": parsed.f, "G": parsed.g}


def generate_section_k(set_aside: str | None) -> FinalDraftSection:
    """Section K — fully programmatic reps/certs assembly (no LLM, no loop).

    Base reps (52.204-8, 52.219-1) + the matching set-aside notice clause +
    52.219-14 for any small-business set-aside.
    """
    clauses = list(_K_BASE)
    sa = (set_aside or "").upper()
    if sa in _K_SET_ASIDE:
        clauses += _K_SET_ASIDE[sa]
    if sa in _SMALL_BIZ_SET_ASIDES:
        clauses.append(_K_LIMITATIONS)

    lines = [
        "K.1 REPRESENTATIONS, CERTIFICATIONS, AND OTHER STATEMENTS OF OFFERORS",
        "",
        "The offeror shall complete the annual representations and certifications "
        "in the System for Award Management (SAM.gov). The following clauses apply "
        "to this solicitation and are incorporated by reference:",
        "",
    ]
    for cite, title in clauses:
        lines.append(f"  • FAR {cite} — {title}")
    if sa in _SMALL_BIZ_SET_ASIDES:
        lines += [
            "",
            "This is a small-business set-aside; offers from concerns that are not "
            "small businesses under the assigned NAICS code will be rejected as "
            "nonresponsive (FAR 52.219-6 / applicable set-aside clause).",
        ]

    text = "\n".join(lines)
    citations = [_clause_citation(c, t, "52") for c, t in clauses]
    return _final("K", text, citations)


def generate_boilerplate(ctx: dict) -> dict[str, FinalDraftSection]:
    """All five boilerplate sections (D, E, F, G, K) keyed by section letter."""
    out = generate_defg(ctx)
    out["K"] = generate_section_k(ctx.get("set_aside"))
    return out
