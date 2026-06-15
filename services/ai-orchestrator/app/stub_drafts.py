"""Demo-day stub drafts (DEMO-REDESIGN-spec §0).

When ``config.AI_STUB_MODE`` is on (Bedrock key rolled), the agent drafters and
coordinator short-circuit to these canned-but-realistic sections so the entire
frontend flow works end-to-end with zero Bedrock spend. The content is
deliberately scenario-specific (not "[stub] would-respond…") so a codebase
reader doesn't dismiss the demo as hollow — it reads like a real draft, and the
live path returns comparable shape once a key lands.

Flip ``AI_STUB_MODE`` OFF (remove the env var) to use real generations.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.agents.schemas import (
    CLINCoverageReport,
    Citation,
    ConsistencyReport,
    FinalDraftSection,
    LMAlignmentReport,
    PartResult,
    SetAsideConsistencyReport,
    SolicitationDraftBundle,
)


def _cite(clause: str, section: str, part: str, text: str) -> Citation:
    return Citation(
        chunk_id=f"stub:{clause}",
        far_part=part,
        far_section=section,
        far_clause=clause,
        snapshot_date=date.today(),
        relevance_score=0.82,
        text=text,
    )


_CANNED_TEXT: dict[str, str] = {
    "C": (
        "C.1 SCOPE\n"
        "The Contractor shall provide all personnel, supervision, tools, and "
        "materials necessary to deliver the services described herein, except as "
        "otherwise specified as Government-furnished. This Statement of Work "
        "defines the requirements for the {title} acquisition.\n\n"
        "C.2 BACKGROUND\n"
        "The Government requires commercial services under NAICS {naics}. Work "
        "shall be performed in accordance with applicable FAR Part 12 commercial-"
        "item procedures and the performance standards in Section C.4.\n\n"
        "C.3 REQUIREMENTS\n"
        "C.3.1 The Contractor shall perform the tasks enumerated in the Performance "
        "Work Statement, meeting the service levels defined in Section C.4.\n"
        "C.3.2 The Contractor shall provide a transition-in plan within ten (10) "
        "business days of award and a transition-out plan ninety (90) days prior "
        "to contract end.\n\n"
        "C.4 PERFORMANCE STANDARDS\n"
        "Performance shall be measured against the Quality Assurance Surveillance "
        "Plan (QASP). Key metrics include availability, responsiveness to service "
        "requests, and adherence to the delivery schedule in Section F."
    ),
    "H": (
        "H.1 SPECIAL CONTRACT REQUIREMENTS\n"
        "H.1.1 Key Personnel. The Contractor shall not substitute key personnel "
        "without the Contracting Officer's prior written approval.\n"
        "H.1.2 Security. Contractor personnel requiring access to Government "
        "systems shall complete the required background investigations consistent "
        "with the place of performance and the agency supplement.\n"
        "H.1.3 Organizational Conflict of Interest. The Contractor shall disclose "
        "any actual or potential OCI in accordance with FAR Subpart 9.5."
    ),
    "L": (
        "L.1 GENERAL INSTRUCTIONS\n"
        "Offerors shall submit proposals in two volumes: Volume I — Technical, and "
        "Volume II — Price. Proposals shall be submitted electronically by the date "
        "and time specified in Section A.\n\n"
        "L.2 VOLUME I — TECHNICAL\n"
        "L.2.1 Technical Approach. Describe the approach to performing the Section C "
        "requirements, including staffing and transition.\n"
        "L.2.2 Past Performance. Provide up to three (3) relevant references for "
        "work of similar size, scope, and complexity within the last three years.\n\n"
        "L.3 VOLUME II — PRICE\n"
        "Provide fully burdened pricing for each CLIN in Section B, including all "
        "option periods. {eval_clause}"
    ),
    "M": {
        "TRADEOFF": (
            "M.1 BASIS FOR AWARD\n"
            "Award will be made to the offeror whose proposal represents the best "
            "value to the Government, considering the non-price factors and price. "
            "Non-price factors, when combined, are significantly more important "
            "than price.\n\n"
            "M.2 EVALUATION FACTORS\n"
            "M.2.1 Technical Approach (most important).\n"
            "M.2.2 Past Performance.\n"
            "M.2.3 Price — evaluated for reasonableness and realism. Each factor in "
            "Section M maps to a corresponding instruction in Section L."
        ),
        "LPTA": (
            "M.1 BASIS FOR AWARD\n"
            "Award will be made on a Lowest-Price Technically-Acceptable (LPTA) "
            "basis. The Government will evaluate technical proposals on an "
            "acceptable/unacceptable basis and award to the lowest-priced offeror "
            "whose proposal is technically acceptable.\n\n"
            "M.2 EVALUATION FACTORS\n"
            "M.2.1 Technical Acceptability — pass/fail against the Section C "
            "requirements and the Section L submission criteria.\n"
            "M.2.2 Price — lowest evaluated price among technically-acceptable "
            "offers, including all option periods."
        ),
    },
}

_CANNED_CITES: dict[str, list[Citation]] = {
    "C": [_cite("12.301", "12.3", "12", "Solicitation provisions and contract clauses for commercial products and services.")],
    "H": [_cite("9.504", "9.5", "9", "Contracting officer responsibilities regarding organizational conflicts of interest.")],
    "L": [_cite("15.204-5", "15.2", "15", "Part IV — Representations and instructions; uniform contract format.")],
    "M": [_cite("15.304", "15.3", "15", "Evaluation factors and significant subfactors.")],
}


def stub_section(
    section_id: str,
    *,
    title: str | None = None,
    naics: str | None = None,
    set_aside: str | None = None,
    eval_approach: str | None = None,
    request_id: str = "",
    run_id: str = "",
) -> FinalDraftSection:
    """Canned FinalDraftSection for an agent-drafted section (C/H/L/M).

    Boilerplate sections (D-G/K) are produced by ``agents.boilerplate`` instead."""
    raw = _CANNED_TEXT.get(section_id)
    if isinstance(raw, dict):  # M — keyed by eval approach
        approach = (eval_approach or "TRADEOFF").upper()
        text = raw.get(approach, raw["TRADEOFF"])
    elif raw is not None:
        eval_clause = (
            "Price will be evaluated on an LPTA basis (see Section M)."
            if (eval_approach or "").upper() == "LPTA"
            else "Price will be evaluated for reasonableness and realism (see Section M)."
        )
        text = raw.format(
            title=title or "this acquisition",
            naics=naics or "n/a",
            eval_clause=eval_clause,
        )
    else:
        text = f"{section_id}.1 (stub) Section {section_id} draft content for review."

    return FinalDraftSection(
        outcome="draft_returned",
        section_text=text,
        section_id=section_id,  # type: ignore[arg-type]
        citations=_CANNED_CITES.get(section_id, []),
        gate_decision="pass",
        requires_human_review=False,
        rerank_top_score=0.82,
        request_id=request_id,
        run_id=run_id,
    )


def _stub_consistency(solicitation_id: str, request_id: str) -> ConsistencyReport:
    return ConsistencyReport(
        solicitation_id=solicitation_id,
        run_id=f"{solicitation_id}:critic:{request_id}",
        lm_alignment=LMAlignmentReport(
            mismatches=[], overall_severity="info",
            model="stub", input_tokens=0, output_tokens=0,
        ),
        set_aside_consistency=SetAsideConsistencyReport(mismatches=[], overall_severity="info"),
        clin_coverage=CLINCoverageReport(gaps=[], overall_severity="info"),
        overall_severity="info",
        blocks_submit=False,
        model_used="stub",
        timestamp=datetime.now(timezone.utc),
    )


def stub_bundle(
    body, *, request_id: str, batch_run_id: str
) -> SolicitationDraftBundle:
    """Full canned coordinator bundle (all Parts) for AI_STUB_MODE batch runs.

    Mirrors the live coordinator's bundle shape so the frontend applyBundle path
    is identical: Part I (C,H,D,E,F,G), II (clause list), III (attachments),
    IV (L,M,K)."""
    from app.agents.boilerplate import generate_boilerplate  # noqa: PLC0415
    from app.agents.coordinator.part_ii import resolve_part_ii_clauses  # noqa: PLC0415
    from app.agents.coordinator.part_iii import pass_through_part_iii  # noqa: PLC0415

    provenances = dict(getattr(body, "provenances", {}) or {})

    def _want(sid: str) -> bool:
        return provenances.get(sid) is None

    boiler = generate_boilerplate({
        "title": body.solicitation_id,
        "naics": body.naics,
        "set_aside": body.set_aside,
        "contract_type": body.contract_type,
        "period_of_performance": getattr(body, "period_of_performance", None),
        "place_of_performance": getattr(body, "place_of_performance", None),
    })

    def _agent_sec(sid: str) -> FinalDraftSection:
        return stub_section(
            sid, title=body.solicitation_id, naics=body.naics,
            set_aside=body.set_aside, eval_approach=getattr(body, "eval_approach", None),
            request_id=request_id, run_id=f"{body.solicitation_id}:part:{request_id}",
        )

    part_i: dict[str, FinalDraftSection] = {}
    for sid in ("C", "H"):
        if _want(sid):
            part_i[sid] = _agent_sec(sid)
    for sid in ("D", "E", "F", "G"):
        if _want(sid) and sid in boiler:
            part_i[sid] = boiler[sid]

    part_iv: dict[str, FinalDraftSection] = {}
    for sid in ("L", "M"):
        if _want(sid):
            part_iv[sid] = _agent_sec(sid)
    if _want("K") and "K" in boiler:
        part_iv["K"] = boiler["K"]

    parts: dict[str, PartResult] = {}
    if part_i:
        parts["I"] = PartResult(part="I", kind="llm_drafted", sections=part_i)  # type: ignore[arg-type]
    parts["II"] = PartResult(
        part="II", kind="programmatic_resolved",
        sections={"I": resolve_part_ii_clauses(
            set_aside=body.set_aside, contract_type=body.contract_type,
            agency_supplement=body.agency_supplement,
        )},
    )
    parts["III"] = pass_through_part_iii(list(getattr(body, "part_iii_attachments", []) or []))
    if part_iv:
        parts["IV"] = PartResult(part="IV", kind="llm_drafted", sections=part_iv)  # type: ignore[arg-type]

    return SolicitationDraftBundle(
        solicitation_id=body.solicitation_id,
        parts=parts,  # type: ignore[arg-type]
        overall_outcome="batch_completed",
        consistency_report=_stub_consistency(body.solicitation_id, request_id),
        pending_interrupts=[],
        request_id=request_id,
        batch_run_id=batch_run_id,
    )
