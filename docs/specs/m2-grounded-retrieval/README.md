# M2 — Grounded retrieval

**Status:** shipped 2026-06-10. 21 ticketed PRs merged on `cj/m2-integration` (handoff commit `c61a2e3`). Coordinator e2e green.

**Entry point on resume:** [`handoff.md`](./handoff.md) — pre-M3 session handoff with verification one-liners + critical gotchas + deferred items.

## What this feature delivered

LangChain v1.0 + Atlas-local 8.0.8 + hybrid retrieval (`$rankFusion`) + Bedrock Rerank 1.0 + tenant-isolated retrieval with locked-passing `req_rag_3` pytest gate + append-only audit log + 4-metric RAGAS eval gate + 10 synthetic solicitations + FAR snapshot ingest + 13-step Angular UCF wizard. Sets the foundation that M1 agentic drafting builds on.

## Files

| File | Role |
|---|---|
| [`handoff.md`](./handoff.md) | Pre-M3 session handoff. Verification one-liners + critical gotchas + known open items. **Read first on any session resuming M1 implementation.** |
| [`retrieval-pipeline.md`](./retrieval-pipeline.md) | Pipeline contracts + stage-by-stage data flow + module layout |
| [`eval-harness.md`](./eval-harness.md) | RAGAS 4-metric + Nova Micro judge + programmatic checks |
| [`rollout.md`](./rollout.md) | The 21-PR rollout plan that shipped M2 |
| [`synthetic-corpus.md`](./synthetic-corpus.md) | Corpus + ingest endpoint internals; synthetic-only constraint |
| [`ui-far-sections.md`](./ui-far-sections.md) | 13-step UCF wizard + provenance + HITL soft-gate surfaces |

## Decisions (ADRs)

ADR-0005 through ADR-0011 in [`docs/adrs/`](../../adrs/) cover M2's locked decisions (retrieval stack, chunking + retrieval pattern, rerank + index lifecycle, security + tenant + audit + HITL, eval + observability + failure modes, implementation manifest, security attack surface).

## What's NOT in M2 (M1 / Phase 1.5 / M3 territory)

- LangGraph `create_agent` for the drafting flow (M1 — ADR-0012).
- `HumanInTheLoopMiddleware` + `MongoDBSaver` checkpointing (M1 — ADR-0012/0013).
- Multi-agent batch coordinator + per-AI-Part fan-out (M1 — ADR-0014).
- Preflight input validation (M1 — ADR-0015).
- Real Nova-Micro LLM-as-judge inside `QueryGuardrails` (Phase 1.5 trigger).
- Audit-log read endpoint exposing the `tool_calls` sub-record (handoff §5.4 open).
- Section J file-persistence backend (M3 / Phase 1.5).
- Source-selection workflow (M3 — REQ-AGT-1..5).

## Counterparts

- M1 agentic drafting feature that builds on this: [`../m1-agentic-drafting/`](../m1-agentic-drafting/)
- Top-level spec index: [`../README.md`](../README.md)
