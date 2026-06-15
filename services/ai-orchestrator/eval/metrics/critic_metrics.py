"""Critic metrics: critic_set_aside_recall, critic_clin_recall,
critic_l_m_alignment_recall, critic_false_positive_rate (design ref §18.8).

Fixture-driven. The two programmatic recalls run the REAL critic tools over
the fixture set (no Bedrock); the L↔M recall needs the LLM tool and is
recorded as null when the fixtures are evaluated offline (the run_m1_metrics
CLI runs it only when Bedrock creds are present).

Fixture row shape (eval/fixtures/m1_critic_fixtures.jsonl)::

    {
      "fixture_id": "fx-001",
      "kind": "set_aside_mismatch" | "clin_gap" | "lm_mismatch" | "known_good",
      "set_aside": "SDVOSB",
      "sections": {"B": "...", "C": "...", "F": "...", "K": "...", "L": "...", "M": "..."},
    }
"""
from __future__ import annotations

from app.agents.critic.tools.clin_coverage import check_clin_coverage
from app.agents.critic.tools.set_aside import check_set_aside_consistency


def _set_aside_flags(fixture: dict) -> bool:
    report = check_set_aside_consistency.func(  # type: ignore[attr-defined]
        set_aside=fixture.get("set_aside"),
        section_k_text=fixture["sections"].get("K"),
    )
    return report.overall_severity != "info"


def _clin_flags(fixture: dict) -> bool:
    s = fixture["sections"]
    report = check_clin_coverage.func(  # type: ignore[attr-defined]
        section_b=s.get("B"), section_c=s.get("C"),
        section_f=s.get("F"), section_l=s.get("L"),
    )
    return report.overall_severity != "info" or any(
        g.severity != "info" for g in report.gaps
    )


def compute_critic_set_aside_recall(fixtures: list[dict]) -> dict:
    """Of injected set-aside mismatches, fraction the programmatic tool flags.

    Phase 1.5 target: = 1.00 (programmatic — trivially achievable, must be
    measured)."""
    cases = [f for f in fixtures if f["kind"] == "set_aside_mismatch"]
    if not cases:
        return {"metric": "critic_set_aside_recall", "value": None, "runs_measured": 0}
    hits = sum(1 for f in cases if _set_aside_flags(f))
    return {
        "metric": "critic_set_aside_recall",
        "value": hits / len(cases),
        "runs_measured": len(cases),
    }


def compute_critic_clin_recall(fixtures: list[dict]) -> dict:
    """Of injected CLIN coverage gaps, fraction flagged. Phase 1.5 target: = 1.00."""
    cases = [f for f in fixtures if f["kind"] == "clin_gap"]
    if not cases:
        return {"metric": "critic_clin_recall", "value": None, "runs_measured": 0}
    hits = sum(1 for f in cases if _clin_flags(f))
    return {
        "metric": "critic_clin_recall",
        "value": hits / len(cases),
        "runs_measured": len(cases),
    }


def compute_critic_false_positive_rate(fixtures: list[dict]) -> dict:
    """Of known-good fixtures, fraction the programmatic critics flag ≥ warn.

    Phase 1.5 target: < 0.10. (LLM L↔M contribution measured only in the
    live-Bedrock run; offline this covers the two programmatic tools.)"""
    cases = [f for f in fixtures if f["kind"] == "known_good"]
    if not cases:
        return {"metric": "critic_false_positive_rate", "value": None, "runs_measured": 0}
    flagged = sum(1 for f in cases if _set_aside_flags(f) or _clin_flags(f))
    return {
        "metric": "critic_false_positive_rate",
        "value": flagged / len(cases),
        "runs_measured": len(cases),
    }


def compute_critic_lm_recall(fixtures: list[dict], *, live: bool = False) -> dict:
    """Of injected L↔M misalignments, fraction the LLM tool flags.

    Needs Bedrock (Nova Lite). Offline runs record null — the metric is
    still emitted so the run summary shows what was NOT measured (no silent
    truncation). Phase 1.5 target: >= 0.85."""
    cases = [f for f in fixtures if f["kind"] == "lm_mismatch"]
    if not cases or not live:
        return {
            "metric": "critic_l_m_alignment_recall",
            "value": None,
            "runs_measured": 0,
            "note": "requires live Bedrock (Nova Lite) — run with creds to measure",
        }
    from app.agents.critic.tools.lm_consistency import verify_l_m_consistency

    hits = 0
    for f in cases:
        report = verify_l_m_consistency.func(  # type: ignore[attr-defined]
            section_l=f["sections"].get("L"), section_m=f["sections"].get("M")
        )
        if report.overall_severity != "info":
            hits += 1
    return {
        "metric": "critic_l_m_alignment_recall",
        "value": hits / len(cases),
        "runs_measured": len(cases),
    }
