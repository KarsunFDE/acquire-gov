# ADR 0009 — RAG eval (RAGAS) + observability + failure-mode handling

Date: 2026-06-01
Status: Proposed (Phase D of retrieval-system planning)
Decision-makers: FDE pair (delivery lead + author)
Phase: 1 — AI Adoption · Milestone M2 (Grounded Retrieval)
Related: ADR-0005..0008 · PRD §7 "eval as the gate" · PRD §6 REQ-RAG-2 (withhold-and-escalate) · PRD §6 REQ-RAG-4 (eval gate blocks grounding regressions)

## Context

Phases A/B/C settled the retrieval substrate, security posture, and HITL gates. Phase D wires the **eval gate that PRD §7 makes non-negotiable**: quality is proven by automated evaluation in CI, not manual inspection. It also locks the observability story (no eval signal is useful if you can't see *where* a regression happened) and the failure-mode contract (the retrieval system has to fail predictably so the audit log can reconstruct why).

## Decisions

### D1 — RAGAS eval gate with four metrics in CI

Source: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/. Four metrics ship as the Phase 1 eval gate:

| Metric | Reference-free? | What it gates | Pass threshold (initial) |
|---|---|---|---|
| **Faithfulness** | Yes | Generated answer is grounded in retrieved context — PRD "grounded-or-withheld" | ≥ 0.85 |
| **Answer Relevancy** | Yes | Answer addresses the query | ≥ 0.80 |
| **Context Precision** | No | Retrieved chunks are relevant to the query | ≥ 0.75 |
| **Context Recall** | No | All ground-truth-relevant chunks are retrieved | ≥ 0.80 |

Thresholds are **initial values**. PRD requires the eval gate to *block grounding regressions* — so the operational rule is: thresholds **never decrease**. Each PR's RAGAS run is compared to `main`'s last-green numbers; any metric below threshold OR below `main - 2%` blocks merge. The thresholds-only-go-up ratchet is the ADR-0009 enforcement of REQ-RAG-4.

**Eval set construction.** Synthetic — `{query, expected_far_section_ids, expected_answer_summary}` tuples generated **from the FAR snapshot** (`docs/reference/far/` per ADR-0005 D5), not human-authored. Why: a human-curated eval set authored by the same engineers tuning prompts is the canonical "author bias" anti-pattern (see D5 below). The FAR snapshot IS the ground truth for the retrieval part; we know which FAR section answers "what are the eval factors for a small-business set-aside" by structure, not by opinion.

Eval set checked into `services/ai-orchestrator/eval/far_eval_set.jsonl` — versioned alongside the FAR snapshot. New eval cases require a separate PR (no co-mingling of "tuning a prompt" and "tuning the eval that gates the prompt").

**CI wiring.** New workflow `.github/workflows/rag-eval-gate.yml` runs on every PR that touches `services/ai-orchestrator/app/retrieval.py`, `services/ai-orchestrator/app/bedrock_client.py`, or `services/ai-orchestrator/eval/`. Job calls `ragas.evaluate(...)`; fails if any metric below threshold OR below `main - 2pp`.

### D2 — Judge model = `amazon.nova-micro-v1:0`; generator stays Sonnet 4.5

Generator (ADR-0003, ADR-0004) = `us.anthropic.claude-sonnet-4-5`. Judge = **`amazon.nova-micro-v1:0`** — different family, different provider, **no self-collusion path**.

Rationale (cited):
- AWS positions Nova Micro as cost floor on Bedrock text LLMs. Source: https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-micro.html, quoted: *"Nova Micro is Amazon's fastest text-only model, optimized for speed and low cost."*
- 128K context window — fits long retrieved-context + multi-chunk eval inputs without splitting.
- Same `boto3.client("bedrock-runtime").invoke_model(...)` + `AWS_BEARER_TOKEN_BEDROCK` path as the generator. No new auth wiring.
- GovCloud-eligible in `us-gov-west-1` (per Nova Micro model card's regional table) — preserves the Phase-2 FedRAMP-High option.

**RAGAS + Bedrock wiring** via LiteLLM provider (https://docs.ragas.io/en/stable/howtos/customizations/customize_models/):

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

RAGAS docs, quoted: *"Ragas may use a LLM and or Embedding for evaluation and synthetic data generation. Both of these models can be customised according to your availability."*

**Judge-drift mitigation: deferred to Phase-1.5 trigger.** Smaller judge models disagree with humans more than larger ones. Phase 1 does NOT reserve cohort or CO time for a 5% spot-check — that would be process surface PRD §4 does not authorize, and would conflict with PRD §7 "eval as the gate... not by manual inspection." Instead: capture **judge-drift signals** structurally — every judge output writes to a `judge_decisions` artifact alongside the eval-set run; a Phase-1.5 follow-up reviews accumulated artifacts only if a threshold ratchet (D1) breaks or eval-set baseline drifts unexpectedly. Escalation lever if drift is real: judge swap to Haiku 4.5 (next-cheapest non-Anthropic-generator option) or threshold recalibration via ADR.

### D3 — Phase 1 observability scope = Bedrock CloudWatch + CloudTrail only

**Bedrock CloudWatch + CloudTrail (auto, no opt-in).** Source: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring.html. Metrics auto-published for `bedrock-runtime`: `Invocations`, `InvocationLatency`, `InputTokenCount`, `OutputTokenCount`. CloudTrail records IAM-level API calls. Cost = standard CloudWatch retention; **zero infrastructure work to enable.** Satisfies REQ-AID-3 ("AI usage is cost-controlled and observable") because input/output tokens are queryable per model per region via the auto-published metrics — no app-side instrumentation needed.

**Bedrock model invocation logging (https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html): EXPLICITLY OFF.** Quote: *"Model invocation logging is disabled by default."* It dumps full prompts + completions to S3 / CloudWatch Logs. Three problems with enabling:
1. Duplicates the prompt/completion content our `audit_log` (ADR-0008 D3) already covers as hashes.
2. Lives outside the role-restricted append-only collection — different access-control surface.
3. For confidential gov data, creates a second persistence target subject to a different retention policy.

CI check (`.github/scripts/verify-bedrock-logging-disabled.sh`) asserts `GetModelInvocationLoggingConfiguration` returns disabled. One-line defensive guard, not an observability tooling artifact. If a future ADR enables it, that ADR must justify against these three concerns.

**App-side OTel: DEFERRED TO PHASE 2.** PRD §4 explicit out-of-scope: *"AIOps / OpenTelemetry rollout, circuit breakers, resilience engineering."* PRD §11 open question: *"How far correlation/tracing is threaded in Phase 1 vs. deferred to the Phase 2 observability rollout"* — this ADR does NOT close that question; Phase 2 does.

Phase 1's correlation primitive is **`audit_log.request_id`** (ADR-0008 D3). Every retrieval-and-generate call writes one audit record; the `request_id` ties together the query, the retrieval candidates, the rerank scores, the citations, the model used, and the HITL outcome. OIG replay reads `audit_log` keyed by `request_id` — no OTel collector, no GenAI semantic conventions, no instrumentation library pin needed.

When Phase 2 rolls out OTel, its ADR will (a) verify GenAI conventions have promoted from Development to Stable, (b) decide whether to add app-side spans alongside `audit_log` or replace `audit_log.request_id` correlation with OTel trace IDs, and (c) own the collector + exporter compose surface. None of that is Phase-1 work.

**Layer 3 — LangSmith SaaS: OFF.** Source: https://docs.langchain.com/langsmith/trace-with-langchain. Enable would be a 3-env-var change (`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`) but it ships prompts + completions to LangChain Inc.'s servers — directly conflicts with PRD §7 "synthetic + FedRAMP-safe." Self-hosted LangSmith Enterprise is a Phase-2 lever, not Phase 1.

**No CloudWatch dashboard JSON artifact in this ADR's verification.** Dashboards are observability tooling. Metrics exist whether or not we ship a dashboard; SRE can build views on demand against the auto-published metric names.

### D4 — Failure modes are explicit per pipeline stage

Each stage of the retrieval pipeline has a documented failure → behavior → audit-log outcome mapping:

| Stage | Failure | Behavior | `audit_log.outcome` |
|---|---|---|---|
| Query embed (Titan v2) | Bedrock 5xx / timeout | Tenacity full-jitter retry per ADR-0004 B1; on exhaustion → 503 `bedrock_unavailable` to caller | `embed_failed` |
| Vector + BM25 retrieval | Mongo down or index `status != READY` | 503 `mongo_unavailable`; **no fallback** to in-memory or single-signal-only | `retrieval_failed` |
| `$rankFusion` hybrid stage | Fusion fails (Preview-status risk per ADR-0006 D5) | Fall back to vector-only (`fulltext_weight=0`); set `degraded_mode=true` in response + audit | `degraded_vector_only` |
| Rerank API call | Bedrock 5xx / timeout / region-down | Tenacity retry; on exhaustion → use top-5 by raw hybrid score (no calibrated relevance score). **Force `requires_human_review=true` unconditionally**; audit `gate_decision: "rerank_unavailable_passthrough"` | `rerank_unavailable_hitl` |
| Rerank top score < 0.3 | Calibrated low confidence | Withhold per ADR-0007 D2 — return "insufficient grounding, escalating" | `withheld` |
| Rerank 0.3 ≤ top score < 0.5 | HITL band | Return result + `requires_human_review=true` | `hitl_pending` |

**Why no fallback to "the other index alone" on hybrid failure:** the Preview-status risk on `$rankFusion` is a real concern (ADR-0006 D5), but vector-only fallback is a *known-evaluated mode* (every dense-query test case in the eval set runs this path). BM25-only-without-vector is *not* evaluated as a standalone retrieval mode in Phase 1 — emitting it as a failure mode would be shipping unproven behavior. Vector-only is the safe degraded path.

**Rerank-unavailable-passthrough behavior** is the key new contract. Two properties enforced:
1. **Always HITL-flag.** Without a calibrated relevance score there is no withhold/pass signal — every response routes to human review.
2. **Audit-log captures the degraded mode.** `gate_decision: "rerank_unavailable_passthrough"` is a queryable field; SREs can dashboard "% of requests in degraded mode" as an availability metric.

**No circuit breaker in Phase 1.** Brownfield Item 3 (missing circuit breaker between evaluation-service and solicitation-service) is **scheduled Phase 2 W4 work** per CLAUDE.md and the brownfield-debt lockfile. Adding one for the Bedrock client now pre-does W4 modernization. Tenacity retry + explicit 5xx mapping (already enforced via ADR-0004) is the Phase 1 contract. Captured here so a future ADR or PR doesn't try to "fix" this gap outside its scheduled week.

### D5 — Anti-pattern appendix

Concrete failure modes the design must avoid, each tied to a mitigating ADR or guideline:

1. **Same model as generator AND judge.** Self-collusion. → D2 above (Nova Micro judge, Sonnet generator).
2. **Tenant filter optional or with a default.** Silent cross-tenant leak. → ADR-0008 D2 (kw-only required arg + locked-passing test).
3. **Re-embedding in-place without dual-write.** Citations drift mid-rebuild. → ADR-0007 D5 (new-index → READY → flip).
4. **Caching LLM responses without prompt-template versioning.** Stale answer survives template change. → ADR-0008 D3 (`prompt_template_version` mandatory in audit record).
5. **Chunks under ~200 chars.** Embedder loses disambiguation signal. → ADR-0006 D1 (1200-char target; recursive split fallback respects separators).
6. **Chunks exceeding the embed model context window.** Silent truncation. → ADR-0006 D1 (1200 chars vs Titan v2 8192-token window — order-of-magnitude headroom).
7. **Enabling Bedrock invocation logging on confidential prompts.** Duplicates content outside the role-restricted audit log. → D3 above (explicitly OFF + CI check).
8. **Storing rerank scores without rerank model ID + version.** Cross-version comparison silently broken. → ADR-0008 D3 (`rerank_model` field per record).
9. **Human-authored eval set written by the same engineers tuning prompts.** Author bias. → D1 above (eval generated from FAR snapshot, separate-PR rule).
10. **Soft-gate (model confidence) overriding hard-gate (statutory authority).** PRD "authority over accuracy" violation. → ADR-0008 D4 (statutory tools always interrupt; confidence never bypasses).
11. **LangSmith SaaS on confidential / FedRAMP-targeted workloads.** Prompts to third-party servers. → D3 above (skipped).
12. **Adding a circuit breaker "while we're in there" to fix brownfield Item 3 early.** Breaks cohort teaching arc. → CLAUDE.md (debt-touch-approved label required) + D4 above (not in scope).
13. **Storing eval-set ground truth in the same MongoDB collection as the corpus.** Retrieval can surface its own ground truth, eval scores inflate. → D1 above (eval set in `services/ai-orchestrator/eval/`, not in `chunks` collection).
14. **Logging raw `gen_ai.retrieval.query.text` for sensitive-flagged tenants.** Tenant-meta data leak through OTel spans. → D3 above (PII-redact per tenant flag).

## Consequences

**Positive:**
- Eval gate (D1) is the CI-blocking proof PRD REQ-RAG-4 requires — grounding regressions don't ship by definition.
- Judge model is different family from generator (D2) — self-collusion structurally impossible.
- Observability covers SRE (CloudWatch auto-metrics) + per-request audit (audit_log.request_id) without sending data to third-party SaaS (LangSmith off). OTel deferred to Phase 2 per PRD §4 + §11.
- Failure-mode table (D4) gives every degraded path a name and an audit-log outcome — operators can dashboard "% degraded" without parsing logs.
- Anti-pattern appendix (D5) is grounded in specific ADR mitigations — not generic "avoid these" advice. Future reviews can cite "this is anti-pattern N from ADR-0009."

**Negative / tradeoffs:**
- App-side OTel deferred to Phase 2 — Phase 1 correlation lives in `audit_log.request_id`. SRE-facing latency/throughput visibility comes from Bedrock CloudWatch auto-metrics only. Trade-off: no app-side span detail showing where in the agent flow time was spent. Accepted because PRD §4 names AIOps/OTel out-of-scope.
- Judge model = Nova Micro means judge calibration vs human is lower-quality than e.g. Sonnet judging itself would be. Judge-drift artifacts written per CI run; Phase-1.5 review triggered only if eval-set ratchet (D1) breaks or baseline drifts. No scheduled human-review time in Phase 1.
- Threshold ratchet (D1) is one-directional — if a deliberate degraded mode is needed (e.g., switching to a cheaper embedder during cost crunch), the ratchet must be **explicitly broken with an ADR**, not silently lowered. Captured as an intentional friction, not a bug.
- No circuit breaker means Bedrock-region brownouts can cascade through Tenacity retries before the 5xx surfaces. SLA tradeoff is documented; Phase 2 W4 is the scheduled fix.
- Rerank-unavailable-passthrough mode (D4) creates a degraded path that's HITL-heavy. If Amazon Rerank's us-west-2 availability is poor, CO toil spikes during outages. Mitigation: CloudWatch alarm on `rerank_unavailable_hitl` outcome rate; if it exceeds some threshold (TBD by ops feedback), escalate to Cohere Rerank 3.5 in us-east-1 as a regional-failover ADR. **Not** Phase 1 scope.

## Verification

- D1: `.github/workflows/rag-eval-gate.yml` exists; running it locally with a known-bad change (delete the tenant pre-filter) causes Context Precision to drop and the job to fail. Threshold-ratchet logic asserts `main`'s last-green numbers + 2pp floor.
- D2: `services/ai-orchestrator/eval/judge.py` instantiates RAGAS with the Nova Micro modelId via LiteLLM. Sonnet 4.5 NOT referenced in eval code. Manual review checklist: "judge != generator" is a PR-template item.
- D3: `verify-bedrock-logging-disabled.sh` passes in CI; Bedrock CloudWatch metrics queryable via console; **no** OTel collector / dashboard JSON / instrumentation packages added in Phase 1.
- D4: integration test `tests/test_retrieval_failure_modes.py` covers each row of the failure-mode table with a mocked-failure injection; asserts the corresponding `audit_log.outcome` value.
- D5: each anti-pattern in the appendix has a referenced ADR section — open question for the senior review: are there mitigations whose tests are missing?

## Open Questions (deferred to Phase 1.5 / Phase 2)

| Q | When |
|---|---|
| Cohere Rerank 3.5 as regional-failover for Amazon Rerank brownouts | Phase 2 ADR, if D4 metrics show it's needed |
| LangSmith self-hosted as trace-UX upgrade | Phase 2, if cohort feedback says OTel + Jaeger isn't enough |
| App-side OTel rollout (including GenAI conventions promotion check) | Phase 2 observability ADR per PRD §4 + §11 |
| Threshold ratchet exception process | Capture as runbook when first deliberate degradation is needed |
| Judge model swap to Haiku 4.5 vs Sonnet for higher-fidelity eval | Phase 1.5 trigger if judge-drift artifacts show disagreement > tolerable rate |
