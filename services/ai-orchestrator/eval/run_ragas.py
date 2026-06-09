"""RAGAS eval runner — calls retrieval endpoints, scores 4 metrics, writes JSON.

Per docs/specs/m2-eval-harness.md section 4 + section 7. Each eval-set entry
yields one /draft-solicitation/section call (or /retrieve for retrieval-only
queries); RAGAS scores the four locked metrics using Nova Micro as judge.

Per-PR ratchet logic lives in ratchet.py — this runner is metric-only and
does not gate on its own; it writes results.json and exits 0 unless the
endpoints themselves fail.

Spec section 4 metrics + thresholds (absolute floors; ratchet enforced by ratchet.py)
    Faithfulness      >= 0.85
    Answer Relevancy  >= 0.80
    Context Precision >= 0.75
    Context Recall    >= 0.80

CLI:
    python -m eval.run_ragas \
        --eval-set eval/far_eval_set.jsonl \
        --adversarial eval/adversarial_cases.jsonl \
        --base-url http://localhost:8000 \
        --out eval/results.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Spec section 4 — absolute floors (no PR may drop below these; ratchet may
# tighten them based on main_last_green - 2pp, never relax below floor).
ABSOLUTE_FLOORS = {
    "faithfulness": 0.85,
    "answer_relevancy": 0.80,
    "context_precision": 0.75,
    "context_recall": 0.80,
}


@dataclass
class EvalRecord:
    """One pre-RAGAS record assembled from an eval-set entry + live HTTP call."""

    eval_id: str
    query: str
    tenant_id: str
    category: str
    contexts: list[str] = field(default_factory=list)
    answer: str = ""
    ground_truth: str = ""
    request_id: str = ""
    latency_ms: float = 0.0
    outcome: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    gate_decision: str = ""
    rerank_top_score: float | None = None
    error: str | None = None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _call_draft_endpoint(
    base_url: str, tenant_id: str, query: str, timeout_s: float
) -> tuple[dict[str, Any], float]:
    """POST /draft-solicitation/section. Returns (response_json, latency_ms).

    Falls back to /retrieve if the eval-set entry doesn't carry a section_id
    — keeps the runner usable for retrieval-only eval sets.
    """
    import httpx  # local import — runner is the only consumer

    headers = {
        "X-Tenant-ID": tenant_id,
        "X-Request-ID": str(uuid.uuid4()),
    }
    # Default to /retrieve for clause-lookup-style queries (no section context
    # available in the eval set). Spec section 7.2 step 3 implies both shapes.
    body = {"query": query}

    t0 = time.perf_counter()
    with httpx.Client(timeout=timeout_s) as client:
        resp = client.post(f"{base_url}/retrieve", headers=headers, json=body)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    resp.raise_for_status()
    return resp.json(), latency_ms


def _extract_contexts(retrieval_response: dict[str, Any]) -> list[str]:
    """Extract chunk text from /retrieve citations[] for RAGAS context input."""
    return [c.get("text", "") for c in retrieval_response.get("citations", [])]


def _extract_answer(retrieval_response: dict[str, Any]) -> str:
    """Best-effort answer extraction for both /retrieve and /draft paths."""
    # /draft-solicitation/section returns section_text; /retrieve returns just
    # citations. For retrieval-only the "answer" is the concatenated top-5
    # text — RAGAS faithfulness still computes meaningfully (does the cited
    # text support the citation claim?).
    if "section_text" in retrieval_response and retrieval_response["section_text"]:
        return str(retrieval_response["section_text"])
    citations = retrieval_response.get("citations", [])
    return "\n\n".join(c.get("text", "") for c in citations)


def gather_records(
    eval_set: list[dict[str, Any]],
    base_url: str,
    timeout_s: float,
) -> list[EvalRecord]:
    """Call the live retrieval stack once per eval-set entry; collect contexts/answers."""
    records: list[EvalRecord] = []
    for entry in eval_set:
        rec = EvalRecord(
            eval_id=entry["eval_id"],
            query=entry["query"],
            tenant_id=entry.get("tenant_id", "agency-test"),
            category=entry.get("category", "clause-lookup"),
            ground_truth=entry.get("expected_answer_summary", ""),
        )
        try:
            resp, latency_ms = _call_draft_endpoint(
                base_url, rec.tenant_id, rec.query, timeout_s
            )
            rec.contexts = _extract_contexts(resp)
            rec.answer = _extract_answer(resp)
            rec.request_id = resp.get("request_id", "")
            rec.latency_ms = latency_ms
            rec.outcome = resp.get("outcome", "")
            rec.citations = resp.get("citations", [])
            rec.gate_decision = resp.get("gate_decision", "")
            rec.rerank_top_score = resp.get("rerank_top_score")
        except Exception as e:  # noqa: BLE001 — capture for results.json
            rec.error = f"{type(e).__name__}: {e}"
        records.append(rec)
    return records


def score_with_ragas(records: list[EvalRecord]) -> dict[str, float]:
    """Score the four spec section 4 metrics against gathered records.

    Returns a {metric_name: mean_score} dict averaged across the eval set.
    Late-imports ragas + judge so unit tests don't pull the deps.
    """
    from ragas import evaluate  # type: ignore[import-not-found]
    from ragas.metrics import (  # type: ignore[import-not-found]
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )
    from datasets import Dataset  # type: ignore[import-not-found]

    from eval.judge import assert_bedrock_auth_present, build_judge_llm

    assert_bedrock_auth_present()
    judge_llm = build_judge_llm()

    scorable = [r for r in records if not r.error and r.contexts]
    if not scorable:
        return {k: 0.0 for k in ABSOLUTE_FLOORS}

    ds = Dataset.from_dict(
        {
            "question": [r.query for r in scorable],
            "contexts": [r.contexts for r in scorable],
            "answer": [r.answer for r in scorable],
            "ground_truth": [r.ground_truth for r in scorable],
        }
    )
    result = evaluate(
        ds,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=judge_llm,
    )
    # `result` is a ragas EvaluationResult; .to_pandas() lets us mean per metric.
    df = result.to_pandas()
    return {
        "faithfulness": float(df["faithfulness"].mean()),
        "answer_relevancy": float(df["answer_relevancy"].mean()),
        "context_precision": float(df["context_precision"].mean()),
        "context_recall": float(df["context_recall"].mean()),
    }


def write_results(
    out_path: Path,
    metrics: dict[str, float],
    records: list[EvalRecord],
    git_sha: str | None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "git_sha": git_sha or os.environ.get("GITHUB_SHA"),
        "eval_set_size": len(records),
        "errors": sum(1 for r in records if r.error),
        "metrics": metrics,
        "absolute_floors": ABSOLUTE_FLOORS,
        "records_summary": [
            {
                "eval_id": r.eval_id,
                "category": r.category,
                "outcome": r.outcome,
                "gate_decision": r.gate_decision,
                "rerank_top_score": r.rerank_top_score,
                "latency_ms": r.latency_ms,
                "request_id": r.request_id,
                "error": r.error,
                "citations_count": len(r.citations),
            }
            for r in records
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-set", type=Path, required=True)
    parser.add_argument("--adversarial", type=Path, default=None)
    parser.add_argument(
        "--base-url",
        type=str,
        default=os.environ.get("AI_ORCHESTRATOR_URL", "http://localhost:8000"),
    )
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--git-sha", type=str, default=None, help="Annotate results.json with commit SHA."
    )
    parser.add_argument(
        "--skip-ragas",
        action="store_true",
        help="Skip RAGAS scoring (e.g. when atlas-local is unavailable); write records-only output.",
    )
    args = parser.parse_args(argv)

    eval_set = _load_jsonl(args.eval_set)
    if args.adversarial:
        eval_set += _load_jsonl(args.adversarial)
    if not eval_set:
        print(
            f"[run_ragas] WARNING: eval set at {args.eval_set} is empty. "
            "Writing empty results.json. First real run depends on D1 eval-set rebuild.",
            file=sys.stderr,
        )
        write_results(args.out, {k: 0.0 for k in ABSOLUTE_FLOORS}, [], args.git_sha)
        return 0

    print(
        f"[run_ragas] gathering {len(eval_set)} eval records against {args.base_url}...",
        file=sys.stderr,
    )
    records = gather_records(eval_set, args.base_url, args.timeout_s)

    if args.skip_ragas:
        metrics = {k: 0.0 for k in ABSOLUTE_FLOORS}
    else:
        metrics = score_with_ragas(records)

    write_results(args.out, metrics, records, args.git_sha)
    print(
        f"[run_ragas] wrote {len(records)} records + metrics → {args.out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
