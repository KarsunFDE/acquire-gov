# M2 Grounded Retrieval — Eval Harness Spec

**Phase 1 · Milestone M2** · Implementer entry point: [`docs/adrs/0009-rag-eval-observability-failure.md`](../../adrs/0009-rag-eval-observability-failure.md)

This spec is **Slice D** previously deferred from [`docs/specs/m2-grounded-retrieval/rollout.md`](./rollout.md) ("RAGAS eval gate — After C11 once retrieval ships"). It owns the full eval-harness shape: RAGAS metrics, Nova Micro judge wiring, programmatic structural checks, CI workflow, eval-set generation, threshold ratchet logic, and the deploy-gate contract that proves PRD REQ-RAG-4 + PRD §7 ("eval as the gate").

## 1. Purpose

PRD §7 makes quality-by-eval non-negotiable: *"Eval as the gate — quality is proven by automated evaluation in CI, not manual inspection."* PRD REQ-RAG-4 requires the eval gate to *"block grounding regressions."* This spec is the CI-blocking proof of those two requirements (ADR-0009 D1). The harness reads from the retrieval endpoints + audit log + corpus locked elsewhere; it adds no new decisions of its own.

## 2. Inputs

```
RETRIEVAL ENDPOINT (from m2-grounded-retrieval/retrieval-pipeline.md):
  POST /retrieve  — returns {outcome, gate_decision, rerank_top_score, citations[], request_id}
  POST /draft-solicitation/section — returns {outcome, section_text, citations[], gate_decision, request_id}

AUDIT LOG (from ADR-0008 D3):
  Every retrieval-and-generate call writes one audit_log record with:
    request_id, tenant_id, query_hash, retrieval.{candidates, rerank_top, gate_decision},
    generation.{citations[], input_tokens, output_tokens, model, prompt_hash, completion_hash},
    outcome

CORPUS (from m2-grounded-retrieval/synthetic-corpus.md):
  FAR Part 15.2 + Part 52 snapshot in docs/reference/far/
  10 synthetic solicitations × 2 agencies (GSA, DoD) × Parts I+II, in docs/reference/synthetic-solicitations/
  ALL eval queries target this corpus; eval set knows ground-truth chunk_ids for each query

PROVENANCE (from m2-grounded-retrieval/ui-far-sections.md):
  Per-section flag {"human"|"ai"|"ai-edited"} — eval does NOT score human-authored sections; only ai/ai-edited paths.
```

## 3. Eval set construction

Per ADR-0009 D1, the eval set is **generated from the FAR snapshot + synthetic-solicitation corpus**, not human-authored — anti-pattern #9 (eval set written by the same engineers tuning prompts) is structurally avoided. The FAR snapshot IS the ground truth: we know which FAR section answers a clause-lookup query by structure, not by opinion.

### 3.1 Generation procedure

| Item | Value |
|---|---|
| Input corpus | `docs/reference/far/` snapshot (ADR-0005 D5, ADR-0011 D7) + `docs/reference/synthetic-solicitations/` lean corpus |
| Output file | `services/ai-orchestrator/eval/far_eval_set.jsonl` |
| Generator tool | `services/ai-orchestrator/eval/build_eval_set.py` |
| Per-FAR-section emission rule | 2-3 queries: 1 clause-lookup, 1 semantic-paraphrase, 1 section-scoped |
| Tenant assignment | All queries assigned `tenant_id = "agency-test"` (eval runs against test-tenant ingest) |
| Initial target size | 80-120 cases (10 docs × ~10 queries each + 6 adversarial) |

### 3.2 Per-line shape

```json
{
  "eval_id": "EV-0001",
  "query": "What does FAR 52.212-4 say about contract terms?",
  "expected_far_section_ids": ["52.212-4"],
  "expected_chunk_ids": ["<known chunk_ids from snapshot>"],
  "expected_answer_summary": "<short reference answer>",
  "tenant_id": "agency-test",
  "category": "clause-lookup | semantic-prose | section-scoped | cross-section | adversarial-jailbreak | adversarial-cross-tenant"
}
```

### 3.3 Adversarial subset

| Property | Value |
|---|---|
| Source | ADR-0011 D6 (existing 3 cases) + 3 cross-tenant fuzz seeds |
| Total adversarial cases | 6 (3 jailbreak + 3 cross-tenant) |
| Generation | **Hand-checked-in only**, not auto-generated (ADR-0009 D5 #9) |
| File | `services/ai-orchestrator/eval/adversarial_cases.jsonl` |
| PR rule | **Adversarial-set PR must be separate from threshold-tuning PR.** Author-bias mitigation (ADR-0009 D5 #9) — same engineer cannot bundle "tune the eval to my prompts" with "add adversarial cases." |

### 3.4 Ground-truth location guard

Eval set lives in `services/ai-orchestrator/eval/`, **never** in the `chunks` collection (ADR-0009 D5 #13 — retrieval surfacing its own ground truth would inflate scores). File-location check: `eval/` is in the gitignored seed-paths list so corpus ingest cannot accidentally embed it.

## 4. RAGAS metrics + thresholds

Per ADR-0009 D1, four metrics ship as the Phase 1 eval gate.

| Metric | Reference-free? | Pass threshold |
|---|---|---|
| Faithfulness | Yes | 0.85 |
| Answer Relevancy | Yes | 0.80 |
| Context Precision | No | 0.75 |
| Context Recall | No | 0.80 |

### 4.1 One-directional ratchet

- Thresholds **never decrease** without an ADR (ADR-0009 D1 + ADR-0009 Consequences "intentional friction").
- Per-PR comparison: each metric must satisfy `metric >= max(absolute_floor, main_last_green - 2pp)`.
- If a deliberate degradation is needed (e.g., cheaper embedder under cost crunch), the ratchet must be **explicitly broken with an ADR**, not silently lowered.
- Threshold values are stored as constants in `services/ai-orchestrator/app/config.py`: `RAGAS_THRESHOLD_FAITHFULNESS`, `RAGAS_THRESHOLD_ANSWER_RELEVANCY`, `RAGAS_THRESHOLD_CONTEXT_PRECISION`, `RAGAS_THRESHOLD_CONTEXT_RECALL` (ADR-0010 D3).

## 5. Judge model wiring

Per ADR-0009 D2: judge = `amazon.nova-micro-v1:0`, generator = `us.anthropic.claude-sonnet-4-5` (ADR-0003). Different family, different provider — **no self-collusion path** (ADR-0009 D5 #1).

### 5.1 RAGAS + Bedrock wiring (verbatim from ADR-0009 D2)

```python
from ragas.llms import llm_factory
import litellm

judge_llm = llm_factory(
    "bedrock/amazon.nova-micro-v1:0",
    provider="litellm",
    client=litellm.completion,
    temperature=0.0,
)
```

### 5.2 Containment rules

| Rule | Enforcement |
|---|---|
| `services/ai-orchestrator/eval/judge.py` is the **only** file allowed to instantiate the Nova Micro client | Manual review checklist + CI grep guard |
| Judge code must **not** import `claude-sonnet` / generator model IDs | Static check: CI step greps `eval/judge.py` for forbidden model strings; non-zero match fails the job |
| Same `AWS_BEARER_TOKEN_BEDROCK` auth as generator | ADR-0009 D2 (no new auth wiring) |
| Judge temperature = 0.0 | Deterministic judge output across runs |

## 6. Programmatic eval checks

Beyond RAGAS, the harness runs **exactly three** structural checks. No others (user-locked clarification).

### 6.1 Check 1 — Citation validity

For every `/retrieve` and `/draft-solicitation/section` response in the eval run:

| Assertion | Source |
|---|---|
| Every `citations[].chunk_id` exists in the post-rerank top-5 | ADR-0011 D3 (`verify_citations` already enforces this; eval also reports the rate) |
| Every `citations[].chunk_id` exists in the `chunks` collection | ADR-0011 D3 |

| Metric | Threshold | Behavior |
|---|---|---|
| `citation_validity_rate = passing / total` | **1.0 (hard)** | Any failure blocks merge |

Surfaced in eval-report PR comment alongside RAGAS metrics.

### 6.2 Check 2 — Cross-tenant leak rate (req_rag_3 fuzz)

Extends `tests/test_cross_tenant_retrieval_impossible.py` adversarial cases (ADR-0011 D6) with auto-generated fuzz:

| Property | Value |
|---|---|
| Seed count per eval run | N = 20 random adversarial queries |
| Seed shape | Jailbreak phrase × random tenant ID combinations |
| Per-query assertion | Retrieve with `tenant_A`; assert no result has `tenant_id != "tenant_A"` |

| Metric | Threshold | Behavior |
|---|---|---|
| `cross_tenant_leak_count` | **0 (hard)** | Any leak blocks merge |

Distinct from the locked-passing test in ADR-0008 D2: that test uses fixed-content; this is randomized fuzz layered on top.

### 6.3 Check 3 — Latency p50/p95 + token-cost regression

For every eval-set query, capture from response + audit log:

| Field | Source |
|---|---|
| `total_latency_ms` | Eval client wall-clock |
| `input_tokens + output_tokens` | `audit_log.generation.*` keyed by `request_id` (ADR-0008 D3) |

Compute p50, p95 latency; sum tokens across the eval run.

**Regression gate — tracking, NOT blocking.** PRD §4 marks AIOps OOS, but PRD REQ-AID-3 keeps per-PR cost tracking in-scope (user-locked clarification accepts this framing):

| Signal | Behavior |
|---|---|
| p95 latency rises >25% vs `main`'s last green | CI warning comment on PR; **do NOT block merge** |
| Total token cost rises >20% vs `main`'s last green | CI warning comment on PR; **do NOT block merge** |

| Artifact | Path |
|---|---|
| Soft-signal baseline | `services/ai-orchestrator/eval/latency_token_baseline.json` |
| Update trigger | Merge to `main` (no PR-level baseline update) |

## 7. CI workflow shape

New file: `.github/workflows/rag-eval-gate.yml`.

### 7.1 Trigger paths

PR touches any of:
- `services/ai-orchestrator/app/retrieval.py`
- `services/ai-orchestrator/app/bedrock_client.py`
- `services/ai-orchestrator/app/rerank.py`
- `services/ai-orchestrator/app/guardrails.py`
- `services/ai-orchestrator/app/citations.py`
- `services/ai-orchestrator/app/prompts/*`
- `services/ai-orchestrator/eval/*`

### 7.2 Steps

| # | Step | Notes |
|---|---|---|
| 1 | Spin up atlas-local + ingest test-tenant FAR + synthetic-solicitation snapshot | Per ADR-0010 D4, D5 |
| 2 | Run `pytest -m req_rag_3` | Locked-passing — ADR-0008 D2 + ADR-0011 D6 + Check 2 fuzz |
| 3 | Run RAGAS eval: `python eval/run_ragas.py --eval-set eval/far_eval_set.jsonl --out eval/results.json` | ADR-0009 D1 |
| 4 | Run Check 1 + Check 3: `python eval/run_programmatic.py --out eval/programmatic.json` | §6.1, §6.3 |
| 5 | Compare to baseline: `python eval/ratchet.py --baseline eval/baseline_main.json --current eval/results.json --current-prog eval/programmatic.json` | §4.1 ratchet logic |
| 6 | Post PR comment with metrics table; fail job on any blocking metric below threshold | RAGAS + Check 1 + Check 2 = blocking; Check 3 = soft warning |

### 7.3 CI required-check name

`rag-eval-gate` — matches the repo's existing required-check matching convention (e.g., `pr-summary-check` recent commit `25ef68c`).

### 7.4 Bedrock budget note

Workflow uses `AWS_BEARER_TOKEN_BEDROCK` from GitHub Actions secret. **Bedrock calls are billable per PR.** Budget envelope:
- Generator: Sonnet 4.5 invocation per eval query.
- Judge: Nova Micro invocation per RAGAS-scored query × 4 metrics.
- Embedding: Titan v2 @ 512 per query (cache-friendly across runs).

Workflow is path-gated (§7.1) precisely to keep cost bounded — non-AI PRs don't trigger it.

## 8. Observability scope

Per ADR-0009 D3 — observability is intentionally minimal in Phase 1.

| Layer | State | Source |
|---|---|---|
| Bedrock CloudWatch auto-metrics (`Invocations`, `InvocationLatency`, `InputTokenCount`, `OutputTokenCount`) | ON (no opt-in needed) | ADR-0009 D3 |
| CloudTrail (IAM-level API call records) | ON (auto) | ADR-0009 D3 |
| Bedrock model invocation logging (full prompts + completions to S3/CW Logs) | **EXPLICITLY OFF** | ADR-0009 D3 |
| App-side OTel / OpenTelemetry | OFF — Phase 2 | ADR-0009 D3 + PRD §4 |
| LangSmith (SaaS or self-hosted) | OFF — never on Phase 1 | ADR-0009 D3 |
| CloudWatch dashboard JSON artifact | NOT shipped — Phase 2 observability tooling | ADR-0009 D3 |

### 8.1 CI guard already scheduled

`.github/scripts/verify-bedrock-logging-disabled.sh` (already scheduled in `m2-grounded-retrieval/rollout.md` Slice C7 + ADR-0009 D3) asserts Bedrock model invocation logging stays OFF on every PR. One-line defensive check, not observability tooling.

### 8.2 Phase 1 correlation primitive

`audit_log.request_id` (ADR-0008 D3). Eval cross-checks token cost via `audit_log` queries keyed by `request_id` — no OTel collector, no GenAI semantic conventions, no instrumentation library pin needed.

## 9. Eval-set drift detection

Per ADR-0009 D2 — judge-drift mitigation deferred to Phase-1.5 trigger.

| Item | Value |
|---|---|
| Per-CI-run artifact | `services/ai-orchestrator/eval/judge_decisions/<run_id>.jsonl` |
| Line shape | `{eval_id, query, judge_verdict, metric, score}` |
| Phase-1.5 review trigger | RAGAS-metric ratchet breaks **OR** eval-set baseline drifts >5pp run-over-run |
| Phase 1 scheduled human review time | **NONE** — PRD §4 OOS, anti-pattern in CLAUDE.md memory (`feedback_solo_adr_critic_pass.md` smuggled-in scheduled-review-time) |
| Escalation lever if drift confirmed | Judge swap to Haiku 4.5 (ADR-0009 D2 Open Questions) or threshold recalibration via new ADR |

## 10. Anti-pattern checks (ADR-0009 D5 restated)

| # | Anti-pattern | Enforcement in this spec |
|---|---|---|
| 1 | Same model as generator AND judge | §5.2 static check — `eval/judge.py` cannot import `claude-sonnet` |
| 9 | Human-authored eval set written by the same engineers tuning prompts | §3.3 separate-PR rule for adversarial cases + §3.1 auto-generation from corpus |
| 13 | Eval-set ground truth stored in same MongoDB collection as the corpus | §3.4 file-location check — `eval/` gitignored from corpus seed paths |

## 11. Inter-spec contracts

| Provider spec | What this eval harness consumes |
|---|---|
| `m2-grounded-retrieval/retrieval-pipeline.md` | Stable `/retrieve` + `/draft-solicitation/section` response shapes; `audit_log.request_id` correlation |
| `m2-grounded-retrieval/synthetic-corpus.md` | Lean corpus (10 docs × 2 agencies × Parts I+II) seeded; chunk_id stable across runs |
| `m2-grounded-retrieval/ui-far-sections.md` | NONE direct — UI does not feed eval; eval calls endpoints directly |

| Consumer | What this eval harness produces |
|---|---|
| `.github/workflows/rag-eval-gate.yml` required check | RAGAS metrics + Check 1 + Check 2 (blocking); Check 3 (soft) |
| `m2-grounded-retrieval/rollout.md` Slice D | Three PR-sized tickets (§13) |

## 12. Module + file layout

| Path | Role |
|---|---|
| `services/ai-orchestrator/eval/build_eval_set.py` | Corpus → eval-set generator (§3.1) |
| `services/ai-orchestrator/eval/far_eval_set.jsonl` | Checked-in eval set (§3.2) |
| `services/ai-orchestrator/eval/adversarial_cases.jsonl` | Checked-in adversarial subset; separate-PR rule (§3.3) |
| `services/ai-orchestrator/eval/judge.py` | Nova Micro via LiteLLM — only file allowed to instantiate the judge client (§5.2) |
| `services/ai-orchestrator/eval/run_ragas.py` | RAGAS runner (§4) |
| `services/ai-orchestrator/eval/run_programmatic.py` | Check 1 + Check 2 + Check 3 runner (§6) |
| `services/ai-orchestrator/eval/ratchet.py` | Compare current vs baseline; emit ratchet decision (§4.1) |
| `services/ai-orchestrator/eval/baseline_main.json` | Last-green RAGAS snapshot from `main` |
| `services/ai-orchestrator/eval/latency_token_baseline.json` | Soft-signal baseline (§6.3) |
| `services/ai-orchestrator/eval/judge_decisions/` | **gitignored** — per-run judge-drift artifact dir (§9) |
| `services/ai-orchestrator/eval/results/` | **gitignored** — per-run RAGAS + programmatic results |
| `.github/workflows/rag-eval-gate.yml` | CI workflow (§7) |

## 13. PR integration with m2-grounded-retrieval/rollout.md

This eval harness becomes **Slice D** added to `m2-grounded-retrieval/rollout.md`. Three PR-sized tickets:

| # | Branch | Title | Type | Depends on |
|---|---|---|---|---|
| **D1** | `cj/m2-d1-eval-set-build` | `build_eval_set.py` + initial `far_eval_set.jsonl` from lean corpus | `feat(eval):` | Slice C1 (FAR snapshot) + corpus-spec C-tickets (synthetic-solicitations seeded) |
| **D2** | `cj/m2-d2-ragas-judge` | `judge.py` + `run_ragas.py` + `baseline_main.json` initial seed | `feat(eval):` | D1 |
| **D3** | `cj/m2-d3-programmatic-checks` | `run_programmatic.py` (Checks 1 + 2 + 3) + `ratchet.py` + `.github/workflows/rag-eval-gate.yml` | `feat(eval):` + `feat(ci):` | D2 |

**Forward-reference:** `m2-grounded-retrieval/rollout.md` will receive an edit adding Slice D rows + a Slice D dependency-graph node after C11. Tracked as "deferred from initial retrieval minimum" in the existing table; promoted to Slice D after C11 lands.

## 14. What this spec does NOT add (scope-out checklist)

| Out-of-scope item | Source |
|---|---|
| OTel / AIOps app-side observability | Phase 2 (PRD §4) + ADR-0009 D3 |
| LangSmith (SaaS or self-hosted) | Never on Phase 1 (ADR-0009 D3) |
| Bedrock invocation logging | Never on (ADR-0009 D3) |
| Scheduled cohort/CO human spot-check budget | PRD §4 OOS (CLAUDE.md memory `feedback_solo_adr_critic_pass.md`) |
| CloudWatch dashboard JSON | Phase 2 observability tooling (ADR-0009 D3) |
| Per-tenant audit-log redaction | Phase 1.5 (ADR-0011 D8) |
| Circuit breaker on Bedrock | W4 cohort work (brownfield Item 3, CLAUDE.md) |
| Eval-as-blocking on latency/token | Kept soft-signal per REQ-AID-3 scope (user-locked) |
| Output-side Guardrails completion filtering | Phase 1.5+ (ADR-0011 D2) |
| Tenant registry collection | PRD §4 OOS (ADR-0010 D7) |

## 15. Open items

| Item | Owner |
|---|---|
| Initial eval-set sizing (80-120) is a **target**; first build-and-run informs whether to expand. | Open — owned by D1 PR outcome |
| Latency p95 baseline cannot exist until first PR merges to `main`. Bootstrap rule: first CI run after D3 merge stamps the baseline. | Open — owned by D3 PR + first post-merge run |
| `_needs_llm_review` threshold in `QueryGuardrails` Layer 2 (ADR-0011 D2) — precision/recall calibration uses eval-set borderline cases as input. | Open — owned by ADR-0011 Open Questions ("Phase D eval cycle") |
| Threshold ratchet exception process (when deliberate degradation is needed) | Open — owned by ADR-0009 Open Questions |
| Judge swap to Haiku 4.5 vs Sonnet for higher-fidelity eval | Open — owned by ADR-0009 Open Questions (Phase-1.5 trigger if drift artifacts show disagreement) |

## When to update this spec

- **Before opening D1**: confirm the lean-corpus shape from `m2-grounded-retrieval/synthetic-corpus.md` matches §3.1's input assumption.
- **After D3 merges**: stamp the initial `baseline_main.json` + `latency_token_baseline.json` from the first post-merge CI run; note any deviation from the 80-120 eval-set target.
- **If a metric ratchet breaks unexpectedly**: trigger the Phase-1.5 judge-drift review (§9) before relaxing the threshold; do not lower thresholds without an ADR (§4.1).
- **If the FAR snapshot is updated** (label `far-snapshot-update-approved`, ADR-0011 D7): re-run `build_eval_set.py` and open a separate D1-style PR for the regenerated `far_eval_set.jsonl` — adversarial-set PR remains separate per §3.3.
