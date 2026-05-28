# acquire-gov — Phase 1 PRD: AI Adoption

| | |
|---|---|
| **Product** | `acquire-gov` — federal acquisitions platform (pre-award + source selection) |
| **Phase** | Phase 1 — AI Adoption |
| **Status** | Living draft — refined in planning sessions |
| **Owner** | FDE pair / delivery lead |
| **Last updated** | 2026-05-28 |

> **This is a PRD, not a plan.** It states the problem, the goals, the boundaries,
> and what "done" looks like — the *what* and *why*. The *how* (endpoints,
> schemas, retrieval approach, gate primitives, thresholds, datastore choices) is
> deliberately **left to the planning sessions** to work out and capture as ADRs.
> Requirements will change as we learn; material changes land in the
> [Change log](#12-change-log), and the [Open questions](#11-open-questions--to-plan)
> are the standing handoff to planning.

**Source of truth:** architecture → [`../../README.md`](../../README.md) · decisions →
[`../adrs/`](../adrs/) · inherited debt → [`../brownfield-debt.md`](../brownfield-debt.md) ·
domain corpus → `domain-knowledge/` (FAR 7/11/12/15/19, DFARS, OIG) · canonical
entity model → external `fde-10-week/training-project/feature-inventory-target.md`.

---

## 1. Background / sponsor objective

The sponsor mandate, as received:

> *"Our contracting officers spend weeks hand-drafting solicitations and running
> source-selection evaluations by hand. We want to pilot AI to compress that
> work — draft solicitations in days not weeks, answer vendor questions against
> the actual regulations, and help the evaluation panel move faster — without an
> OIG auditor ever being able to say the system made a decision a human was
> supposed to make, or cited a regulation that doesn't exist."*

That is the whole brief. It does not say which endpoints, which models, what
"grounded" means, or where a human must stay in the loop — that's ours to plan.
Phase 1 disseminates it to a single intent: **introduce AI into the
solicitation → evaluation → award workflow, with every irreversible or
statutorily-reserved decision routed through a human, and every AI output
traceable to a real source and an accountable actor.**

Phase 1 is **adoption**, not modernization. We add AI on top of the platform as
it stands. Fixing the legacy stack itself is Phase 2 (§12).

## 2. Current state

`acquire-gov` is a running four-service system (full diagram in the
[README](../../README.md)):

| Service | Stack | Port |
|---------|-------|------|
| `frontend/` | Angular 17 SPA — contracting-officer UX | 4200 |
| `services/api-gateway/` | Spring Boot 2.7.18 + OAuth2 Resource Server (Java 11) | 8080 |
| `services/solicitation-service/` | Spring Boot 2.7.18 + Postgres + MongoDB (Java 11) | 8081 |
| `services/evaluation-service/` | Spring Boot 2.7.18 (Java 11) | 8082 |
| `services/ai-orchestrator/` | Python 3.11 + FastAPI + LangChain v1.0 (Bedrock) | 8000 |

The platform runs, but the AI path today returns **raw, ungrounded model output
with no validation** — it will confidently emit a solicitation citing a FAR
clause that doesn't apply or doesn't exist. That is the OIG-defensibility problem
the sponsor named, and it's the thread Phase 1 pulls.

The platform also carries **12 documented debt items** (see
[`brownfield-debt.md`](../brownfield-debt.md)). Adoption work will surface — and
in some cases incidentally close — a few of them; deliberate modernization of the
rest is Phase 2.

## 3. Goals

| # | Goal | Done = |
|---|------|--------|
| G1 | Compress solicitation drafting | A CO produces a reviewable, structured draft on demand, in minutes. |
| G2 | Ground every AI answer in real regulation | Authoritative answers cite the actual FAR/DFARS source; ungrounded ones are withheld, not shipped. |
| G3 | Make source-selection assistance safe | The evaluation → consensus → SSA → award flow runs with a human gate on every reserved/irreversible step. |
| G4 | Be auditable by default | Every AI-assisted decision is reconstructable: who, what, when, under which authority. |
| G5 | Be measurably correct | AI quality is gated by automated evaluation, and regressions are caught before they ship. |

## 4. Non-goals (Phase 1)

Boundaries are deliberate and sharp. Out of scope for Phase 1 (most are Phase 2):

- ❌ Framework/runtime modernization (Spring Boot/Java/`javax`→`jakarta`/AWS SDK hops).
- ❌ AI-security hardening of the legacy debt (auth, input sanitization, image pinning).
- ❌ Full multi-tenant isolation across all services (Phase 1 covers the retrieval boundary only).
- ❌ AIOps / OpenTelemetry rollout, circuit breakers, resilience engineering.
- ❌ Production-incident response drill.
- ❌ **Real** payment, funds-transfer, or award-execution authority — modeled and gated, never actually executed.
- ❌ Live PII / CUI — synthetic data only.
- ❌ Angular major-version upgrade (stays on 17).
- ❌ Managed Bedrock products (Knowledge Bases, Agents, Guardrails) — hand-built in Phase 1.

## 5. Users

| Persona | Role | What Phase 1 gives them |
|---------|------|--------------------------|
| **Contracting Officer (CO)** | Owns the solicitation; warrant holder | AI-drafted solicitations + grounded vendor answers to review; approval authority on every draft and amendment. |
| **Source Selection Authority (SSA)** | Makes the source-selection decision | An assisted evaluation flow that surfaces a recommendation but **stops** for the SSA's non-delegable decision before any award. |
| **Evaluation panel (SSEB)** | Scores proposals | Agent-assisted triage and scoring support; visibility into decisions before consensus. |
| **OIG auditor** | After-the-fact accountability | A replayable trail: who decided what, when, under which authority, citing which regulation. |

## 6. Capability requirements

Phase 1 delivers three capabilities in sequence; each one's gap is why the next
exists. Requirements are stated as outcomes — **the planning sessions decide how.**

### M1 — LLM-assisted solicitation drafting
- **REQ-AID-1** The platform drafts a structured solicitation from a CO's prompt. *Done:* a CO generates a reviewable draft on demand.
- **REQ-AID-2** AI output is safe to consume — no malformed or ungrounded content silently passes downstream. *Done:* bad model output is caught before it reaches another service or the CO.
- **REQ-AID-3** AI usage is cost-controlled and observable. *Done:* cost is attributable per tenant/feature and runaway spend is bounded.
- **REQ-AID-4** No AI-drafted solicitation is issued without CO approval *(HITL)*. *Done:* issuance is impossible without a recorded human decision.

### M2 — Grounded retrieval
- **REQ-RAG-1** Regulatory answers come from the actual FAR/DFARS corpus, with citations. *Done:* every authoritative answer traces to a source clause.
- **REQ-RAG-2** Low-confidence or ungrounded answers are withheld and escalated to a human, never shipped to a vendor *(HITL)*. *Done:* below-bar answers route to review instead of returning.
- **REQ-RAG-3** One agency can never retrieve another agency's content. *Done:* cross-tenant retrieval is impossible and proven by test.
- **REQ-RAG-4** Retrieval quality is measured and protected from regression. *Done:* an evaluation gate blocks changes that degrade grounding.

### M3 — Agentic source-selection workflow
- **REQ-AGT-1** The evaluation → consensus → SSA → award workflow runs as an assisted agentic flow on synthetic evaluations. *Done:* the flow runs end to end and produces a decision-document draft plus a gated award step.
- **REQ-AGT-2** Every statutorily-reserved or irreversible step stops for the responsible human; the agent cannot pass it (FAR 15.308 SSA decision; FAR 5.705 award; FAR 15.206 amendment) *(HITL)*. *Done:* no code path auto-executes a reserved/irreversible step.
- **REQ-AGT-3** A paused decision survives a real-world human delay (hours or days) and resumes without loss or regeneration. *Done:* a run pauses for the SSA and resumes intact after a restart.
- **REQ-AGT-4** Every gated decision is auditable — who decided, what they saw, under which authority. *Done:* an OIG reviewer can reconstruct each decision from the trail alone.
- **REQ-AGT-5** The acquisitions data answers the relational questions a CO actually asks. *Done:* CO traversal questions (e.g. "this vendor's contracts with red CPARs") are answerable at interactive speed.

## 7. Principles (cross-cutting)

These hold across every capability and are non-negotiable; *how* they're
implemented is planned.

- **Authority over accuracy.** Gates exist because of accountability, not model
  quality. Statutorily-reserved and irreversible steps are **hard** gates;
  model confidence never downgrades a hard gate to a soft one.
- **Right-sized HITL.** Classify each decision by reversibility × blast-radius.
  Gate what must be gated — no skipped reserved decisions, no gate sprawl.
- **Grounded or withheld.** No authoritative answer ships without a real
  citation; when grounding is weak, escalate to a human rather than guess.
- **Auditable by default.** Sensitive/AI-assisted decisions write an append-only,
  OIG-replayable record. (The legacy audit gaps themselves are a Phase 2 fix.)
- **Synthetic + FedRAMP-safe.** Synthetic data only; AWS Bedrock is the sole LLM
  path (FedRAMP inheritance, ADR-0002); no direct third-party model API.
- **Eval as the gate.** Quality is proven by automated evaluation in CI, not by
  manual inspection.

## 8. Domain model

Federal acquisitions is modeled as a **graph of ~17 entities** (canonical
enumeration in the external `feature-inventory-target.md`). The spine:

`Vendor ↔ Proposal ↔ Evaluation ↔ Award ↔ ContractModification ↔ Cpar`

CO work is inherently relational ("every contract this vendor won with red
CPARs"), so the model must support multi-hop traversal at interactive speed
(REQ-AGT-5). Volumes are modest (~100 vendors / ~500 proposals / ~80 active
contracts per agency) — the *representation* choice is a planning decision (§11).

## 9. Success metrics & Phase 1 exit

Phase 1 is done when the three capabilities work end to end and the following
hold (these are also the gate dimensions):

| Dimension | Exit outcome |
|-----------|--------------|
| Agent-flow architecture | The evaluation→consensus→SSA→award flow runs end to end on synthetic data and survives a human-delay pause/resume. |
| Federal-authority semantics | Every hard gate names its governing FAR clause; no reserved/irreversible step can be auto-executed. |
| HITL appropriateness | Gates are right-sized by reversibility × blast-radius — nothing reserved is skipped, nothing trivial is over-gated. |
| Relational/graph integration | The CO's traversal questions are answerable within an interactive latency budget. |
| Debt acknowledgement | The team can name which inherited debt their AI work touched, surfaced, or incidentally closed — and which is deferred to Phase 2. |

Product signals: solicitation first-draft turnaround weeks → minutes (G1); zero
ungrounded authoritative answers in evaluation (G2); 100% of hard-gate decisions
produce an audit record (G4).

## 10. Constraints & scope caps

- **One core workflow.** Solicitation → evaluation → award. Other acquisition
  lifecycle stages are referenced, not built.
- **No real authority.** Payment, funds transfer, and award execution are
  simulated via mock services + audit logs only.
- **Synthetic data only.** No live PII/CUI anywhere.
- **Adopt, don't modernize.** Don't pre-fix inherited debt that Phase 2 owns;
  surface it, note the blast radius, defer it.

## 11. Open questions / to-plan

The deliberate handoff to the planning sessions. These are decided there and
captured as ADRs — not pre-answered here.

- Drafting output schema + the fields a real CO solicitation template needs.
- Retrieval approach (chunking, embedding model, dense/sparse/hybrid, reranking) to hit grounding + latency.
- The "withhold / escalate" confidence bar and how it's measured.
- Drafting UX: synchronous vs. streaming delivery.
- Gate implementation primitives + how a paused run is persisted across a multi-day human delay.
- Graph representation (dedicated graph store vs. relational traversal) and its FedRAMP control-cost trade-off.
- How far correlation/tracing is threaded in Phase 1 vs. deferred to the Phase 2 observability rollout.
- Which inherited debt items are in-bounds to close as a side effect vs. strictly deferred.

## 12. Phase 2 outline (refined at Phase 1 close-out)

Sketch only, so Phase 1 decisions don't corner it. Phase 2 = **modernization +
operationalization**: framework/runtime/SDK modernization; AI-security hardening
of the inherited debt; reliability + AIOps + observability; a resilience-under-load
exercise; and client deliverability (runbook, ADR catalog, eval report, security
attestation, handoff). A dedicated Phase 2 PRD supersedes this section.

## 13. Change log

| Date | Change | Driver |
|------|--------|--------|
| 2026-05-28 | Initial Phase 1 PRD disseminated from sponsor objective. | Phase 1 kickoff |
| 2026-05-28 | Re-cut to PRD altitude — moved technical/implementation detail out to planning (kept outcomes, principles, boundaries). | Altitude correction |
