# M1 — Agentic draft-solicitation workflow

**Status:** active. Phase 0 not yet started.

**Entry point:** [`tracker.md`](./tracker.md) — phase status + crash-recovery checklist + active-phase block.

## What this feature does

Re-shapes `POST /draft-solicitation/section` from M2's single-pass `ChatBedrockConverse` call into a LangChain v1.0 agentic workflow. Adds a multi-agent batch coordinator (per FAR UCF Part fan-out), a cross-section consistency critic, a preflight input-validation gate, and a CO HITL interrupt+resume flow that survives multi-day pauses.

## Files

| File | Role |
|---|---|
| [`tracker.md`](./tracker.md) | **Live state.** Phase status table + crash-recovery checklist + status-update protocol. Read first on every session resume. |
| [`design-reference.md`](./design-reference.md) | Endpoint contracts, Pydantic schemas, tool internals, audit shape, middleware wiring. The *what*. |
| [`topology.html`](./topology.html) | Visual: multi-agent topology with hover-on-block Pydantic schemas. Open in a browser. |
| [`phases/0-foundation.md`](./phases/0-foundation.md) | Phase 0 — schemas + config + checkpointer (3 PRs, backend-only) |
| [`phases/1-single-section.md`](./phases/1-single-section.md) | Phase 1 — single-section happy path (7 PRs, vertical slice) |
| [`phases/2-hitl-resume.md`](./phases/2-hitl-resume.md) | Phase 2 — HITL interrupt + resume + abandon (4 PRs, vertical slice) |
| [`phases/3-batch-coordinator.md`](./phases/3-batch-coordinator.md) | Phase 3 — batch coordinator with per-AI-Part fan-out (6 PRs, vertical slice) |
| [`phases/4-consistency-critic.md`](./phases/4-consistency-critic.md) | Phase 4 — consistency critic (4 PRs, vertical slice) |
| [`phases/5-hardening.md`](./phases/5-hardening.md) | Phase 5 — eval metrics + e2e smoke + close-out handoff (3 PRs) |

## Decisions (ADRs)

| ADR | Scope |
|---|---|
| [`docs/adrs/0012-*`](../../adrs/0012-agentic-draft-solicitation-workflow.md) | Single-section agent baseline |
| [`docs/adrs/0013-*`](../../adrs/0013-multi-agent-coordinator-and-critic.md) | Multi-agent topology mechanics (Coordinator + Critic + checkpointer + rate-limit + endpoints) |
| [`docs/adrs/0014-*`](../../adrs/0014-per-far-part-batch-fan-out.md) | Per-AI-Part fan-out + L↔M FAR factual correction (supersedes 0013 D1/D9) |
| [`docs/adrs/0015-*`](../../adrs/0015-preflight-input-validation.md) | Preflight input-validation gate + wizard reactive-forms migration |

## Counterparts

- M2 grounded retrieval foundation that this builds on: [`../m2-grounded-retrieval/`](../m2-grounded-retrieval/)
- Top-level spec index: [`../README.md`](../README.md)
