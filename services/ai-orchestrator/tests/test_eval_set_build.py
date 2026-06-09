"""Unit tests for eval.build_eval_set — structural generator (spec §3.1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # so `import eval...` resolves under pytest

from eval.build_eval_set import (  # noqa: E402
    EvalCase,
    build_eval_cases,
    write_jsonl,
)

FIXTURES = Path(__file__).parent / "fixtures"
FAR_FIXTURE = FIXTURES / "far"
SOL_FIXTURE = FIXTURES / "synthetic-solicitations"


@pytest.mark.eval_harness
def test_build_eval_cases_emits_clause_lookup_per_far_section() -> None:
    cases = build_eval_cases(FAR_FIXTURE, SOL_FIXTURE)
    # Expect clause-lookup for every Part 52 clause and Part 15.2 subsection in fixture.
    far_ids = {fid for c in cases for fid in c.expected_far_section_ids}
    assert "52.212-4" in far_ids
    assert "52.219-14" in far_ids
    assert "52.204-7" in far_ids
    assert "15.203" in far_ids
    assert "15.207" in far_ids


@pytest.mark.eval_harness
def test_build_eval_cases_emits_three_query_kinds_per_part52_clause() -> None:
    cases = build_eval_cases(FAR_FIXTURE, SOL_FIXTURE)
    cats_for_52_212_4 = [
        c.category for c in cases if c.expected_far_section_ids == ("52.212-4",)
    ]
    # Part 52 clauses get clause-lookup + semantic-prose + section-scoped.
    assert "clause-lookup" in cats_for_52_212_4
    assert "semantic-prose" in cats_for_52_212_4
    assert "section-scoped" in cats_for_52_212_4


@pytest.mark.eval_harness
def test_build_eval_cases_eval_ids_are_unique_and_sorted() -> None:
    cases = build_eval_cases(FAR_FIXTURE, SOL_FIXTURE)
    eval_ids = [c.eval_id for c in cases]
    assert len(eval_ids) == len(set(eval_ids))
    # Monotonic increasing — supports stable diff review.
    assert eval_ids == sorted(eval_ids)


@pytest.mark.eval_harness
def test_build_eval_cases_all_tenant_id_is_agency_test() -> None:
    # Spec §3.1: tenant_id = "agency-test" for every query.
    cases = build_eval_cases(FAR_FIXTURE, SOL_FIXTURE)
    assert cases  # sanity
    assert all(c.tenant_id == "agency-test" for c in cases)


@pytest.mark.eval_harness
def test_build_eval_cases_expected_chunk_ids_empty_at_build_time() -> None:
    # Spec §3.2 + spec note: expected_chunk_ids populated post-ingest.
    cases = build_eval_cases(FAR_FIXTURE, SOL_FIXTURE)
    assert all(c.expected_chunk_ids == () for c in cases)


@pytest.mark.eval_harness
def test_build_eval_cases_robust_to_missing_far_dir(tmp_path: Path) -> None:
    nonexistent_far = tmp_path / "no-far"
    nonexistent_sol = tmp_path / "no-sol"
    cases = build_eval_cases(nonexistent_far, nonexistent_sol)
    assert cases == []


@pytest.mark.eval_harness
def test_build_eval_cases_robust_to_missing_solicitations_dir(tmp_path: Path) -> None:
    # FAR-only build should still produce structural queries.
    cases = build_eval_cases(FAR_FIXTURE, tmp_path / "no-sol")
    assert cases  # FAR-only generates clause-lookup at minimum


@pytest.mark.eval_harness
def test_write_jsonl_roundtrip(tmp_path: Path) -> None:
    cases = build_eval_cases(FAR_FIXTURE, SOL_FIXTURE)
    out = tmp_path / "out.jsonl"
    n = write_jsonl(cases, out)
    assert n == len(cases)
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == n
    parsed = [json.loads(line) for line in lines]
    # Every record carries the spec §3.2 fields.
    required = {
        "eval_id",
        "query",
        "expected_far_section_ids",
        "expected_chunk_ids",
        "expected_answer_summary",
        "tenant_id",
        "category",
    }
    for rec in parsed:
        assert required.issubset(rec.keys())


@pytest.mark.eval_harness
def test_eval_case_categories_within_known_set() -> None:
    # Spec §3.2 enumerates the legal category strings.
    allowed = {
        "clause-lookup",
        "semantic-prose",
        "section-scoped",
        "cross-section",
        "adversarial-jailbreak",
        "adversarial-cross-tenant",
    }
    cases = build_eval_cases(FAR_FIXTURE, SOL_FIXTURE)
    seen = {c.category for c in cases}
    assert seen.issubset(allowed), f"unexpected categories: {seen - allowed}"
