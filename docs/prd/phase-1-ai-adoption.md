# acquire-gov — Phase 1 PRD: AI Adoption

| | |
|---|---|
| **Product** | `acquire-gov` — federal acquisitions platform (pre-award + source selection) |
| **Phase** | Phase 1 — AI Adoption |
| **Status** | Living draft — refined at each phase planning checkpoint |
| **Owner** | FDE pair / delivery lead |
| **Last updated** | 2026-05-28 |
| **Supersedes** | — |

> **This is a living document.** It is written from a loosely-scoped sponsor
> objective and disseminated into actionable requirements with the knowledge we
> have today. Not everything is known up front. Requirements are expected to
> change as the engagement deepens; every material change is recorded in the
> [Change log](#13-change-log). Treat the [Open questions](#11-known-unknowns--open-questions)
> as a standing backlog, not as gaps to hide.

**Source-of-truth pointers**

- Architecture + service inventory → [`../../README.md`](../../README.md)
- Architecture decisions → [`../adrs/`](../adrs/) (`0001-microservices-architecture`, `0002-bedrock-as-llm-anchor`)
- Known platform debt → [`../brownfield-debt.md`](../brownfield-debt.md)
- Canonical entity model + data volumes → external `fde-10-week/training-project/feature-inventory-target.md` (not in this repo; treated as authoritative where it conflicts with §9)
- Regulatory corpus → `domain-knowledge/` (FAR Parts 7/11/12/15/19, DFARS, OIG)

---

## 1. Background / Sponsor objective

The sponsor mandate, as received:

> *"Our contracting officers spend weeks hand-drafting solicitations and running
> source-selection evaluations by hand. We want to pilot AI to compress that
> work — draft solicitations in days not weeks, answer vendor questions against
> the actual regulations, and help the evaluation panel move faster — without an
> OIG auditor ever being able to say the system made a decision a human was
> supposed to make, or cited a regulation that doesn't exist."*

That is the whole brief. It does not say which endpoints, which models, what
"grounded" means, or where a human must stay in the loop. Phase 1 is the
disseminated plan: **introduce AI capability into the existing acquisitions
platform at the solicitation → evaluation → award workflow, with every
irreversible or statutorily-reserved decision routed through a human, and every
AI output traceable to a citable source and an accountable actor.**

Phase 1 is **adoption**, not modernization. We add AI on top of the platform as
it stands today. Fixing the legacy stack itself (framework hops, security
hardening, observability rollout) is Phase 2 — see §12.

## 2. Current state

`acquire-gov` is a running four-service system (see [README](../../README.md) for
the full diagram):

| Service | Stack (today) | Port |
|---------|---------------|------|
| `frontend/` | Angular 17 SPA — contracting-officer UX | 4200 |
| `services/api-gateway/` | Spring Boot 2.7.18 + Spring Cloud Gateway + OAuth2 Resource Server (Java 11) | 8080 |
| `services/solicitation-service/` | Spring Boot 2.7.18 + JPA (Postgres) + MongoDB (Java 11) — FAR/DFARS solicitation CRUD | 8081 |
| `services/evaluation-service/` | Spring Boot 2.7.18 (Java 11) — evaluation-panel coordination | 8082 |
| `services/ai-orchestrator/` | Python 3.11 + FastAPI + LangChain v1.0 + Pydantic v2 + boto3 | 8000 |
| Datastores | PostgreSQL (5432), MongoDB (27017) + Atlas Vector Search | — |
| LLM | AWS Bedrock (Claude); `BEDROCK_MODEL_ID` pinned one generation behind GA | — |

The platform carries **deliberate, documented debt** (12 items, see
[`brownfield-debt.md`](../brownfield-debt.md)). Phase 1 interacts with a subset
of these — some get closed as a side effect of adoption work, some are merely
surfaced and explicitly deferred to Phase 2:

- **Closed in Phase 1:** Item 4 (no structured-output validation), Item 5
  (pre-v1.0 LangChain), Item 7 (unused `pinecone-client`), Item 10 (no
  multi-tenant boundary on retrieval).
- **Partially addressed in Phase 1:** Item 6 (correlation IDs threaded on the AI
  path only), Item 12 (first real CI quality gate established via the eval
  harness). Full fixes are Phase 2.
- **Surfaced, deferred to Phase 2:** Item 2 (audit-log race), Item 3 (no circuit
  breaker).
- **Untouched in Phase 1:** Items 1, 8, 9, 11 (Phase 2 modernization / AI
  security).

The concrete failure that motivates the whole phase: the AI drafting path today
returns raw model output with **no grounding and no validation** — it will
confidently emit a solicitation that cites a FAR clause that does not apply (or
does not exist). That is the OIG-defensibility problem the sponsor named, and it
is the thread Phase 1 pulls.

## 3. Goals

| # | Goal | Phase 1 done = |
|---|------|----------------|
| G1 | Compress solicitation drafting | A CO can produce a structured, validated solicitation draft from a prompt, in minutes, through `/draft-solicitation`. |
| G2 | Ground all AI output in real regulation | Vendor Q&A and clause references are retrieved from the FAR/DFARS corpus and carry citations; ungrounded/low-faithfulness answers are withheld, not shipped. |
| G3 | Make source-selection assistance safe | The evaluation → consensus → SSA → award workflow runs as an agentic flow with **hard human gates** on every statutorily-reserved or irreversible step. |
| G4 | Be auditable by default | Every AI-assisted decision writes an append-only audit record naming the actor, the before/after state, and the governing FAR citation, replayable for an OIG review. |
| G5 | Be measurably correct | An evaluation harness gates AI quality (faithfulness/relevance) and blocks regressions before they ship. |

## 4. Non-goals (Phase 1)

Explicitly **out of scope** for Phase 1 (most are Phase 2 — see §12):

- ❌ Framework/runtime modernization — Spring Boot 2.7→4, Java 11→21,
  `javax`→`jakarta`, AWS SDK v1→v2. Phase 2.
- ❌ AI-security hardening of the legacy debt — Items 1 (JWT skip), 9 (input
  sanitization), 11 (`:latest` images). Phase 2.
- ❌ Full multi-tenant deep-dive — Phase 1 enforces the **retrieval** boundary
  (Item 10); full tenant isolation across all services is Phase 2.
- ❌ AIOps / OpenTelemetry rollout, circuit breakers, resilience engineering
  (Items 3, 6 end-state). Phase 2.
- ❌ Mid-sprint production-incident response drill. Phase 2 (W4).
- ❌ **Real** payment, funds-transfer, or award-execution authority. Award
  *recording* is modeled and gated; actual disbursement/award authority is
  simulated via mock services only.
- ❌ Live PII / CUI handling. Synthetic data only.
- ❌ Angular major-version upgrade (stays on 17).
- ❌ Managed Bedrock products (Knowledge Bases, Agents-for-Bedrock, Guardrails).
  Phase 1 hand-builds with LangChain + Atlas. Managed services are Phase 2 (W5).

## 5. Users

| Persona | Role | What Phase 1 gives them |
|---------|------|--------------------------|
| **Contracting Officer (CO)** | Owns the solicitation; warrant holder | AI-drafted solicitations to review; grounded answers to vendor questions; the approval authority on every AI draft (HITL #1) and amendment (FAR 15.206). |
| **Source Selection Authority (SSA)** | Makes the source-selection decision | An agentic evaluation workflow that surfaces a consensus + SSDD draft, but **stops** for the SSA's non-delegable approval (FAR 15.308) before any award is recorded (FAR 5.705). |
| **Evaluation panel member (SSEB)** | Scores proposals | Agent-assisted intake triage and scoring support; visibility into supervisor decisions before consensus. |
| **OIG auditor** | After-the-fact accountability | A replayable audit trail: who decided what, when, under which authority, citing which regulation. |

## 6. Scope — the AI Adoption capability stack

Phase 1 delivers three capability milestones in sequence. Each builds on the
prior one; each one's gap is the reason the next one exists.

- **M1 — LLM-assisted solicitation drafting.** Production-discipline Bedrock
  invocation behind `/draft-solicitation`: structured output, validation, cost
  control, and the first human gate.
- **M2 — Grounded retrieval (RAG).** A FAR/DFARS clause library in Atlas Vector
  Search; hybrid retrieval with citations; a tenant boundary; a faithfulness
  gate that escalates low-confidence answers to a human instead of shipping them.
- **M3 — Agentic source-selection workflow.** The grounded retrieval becomes a
  *tool* an agent uses. A single-agent intake-triage flow, then a multi-agent
  `evaluator → consensus → ssa_review_ssdd → record_award` LangGraph state
  machine with hard, FAR-anchored human interrupts and durable checkpointing.

Phase 1 closes when M1–M3 are demonstrable end to end and pass the exit criteria
in §10.

## 7. Functional requirements

Acceptance criteria are written to be testable. IDs are stable references for the
traceability matrix (maintained separately by delivery) and the change log.

### M1 — LLM-assisted solicitation drafting

- **REQ-AID-101 — Drafting endpoint.** `POST /draft-solicitation` (ai-orchestrator)
  accepts a CO drafting request and returns a structured solicitation draft via
  Bedrock `InvokeModel`.
  *Accept:* given a valid request, returns a draft conforming to the
  `SolicitationDraft` schema; the response is consumable by `solicitation-service`
  without a null-field crash.
- **REQ-AID-102 — Structured-output validation.** Model output is parsed and
  re-emitted through a strict Pydantic schema (`extra="forbid"`); malformed or
  null required fields (e.g. `clause_id`) are rejected or repaired, never passed
  through raw. *(Closes debt Item 4.)*
  *Accept:* a fixture of malformed Bedrock output never reaches a downstream
  service; validation failures are logged and surfaced, not swallowed.
- **REQ-AID-103 — Resilience on the model call.** Bedrock calls retry on
  throttling/5xx with exponential backoff + jitter, bounded by a max attempt
  count.
  *Accept:* simulated 429s recover within the retry budget; exhausted retries
  return a typed error, not a 500 stack trace.
- **REQ-AID-104 — Cost telemetry.** Every model call records
  `input_tokens`, `output_tokens`, `model_id`, `feature`, `tenant_id`.
  *Accept:* a day's calls can be aggregated to a per-tenant, per-feature spend.
- **REQ-AID-105 — Cost guardrails.** Requests carry an idempotency key
  (duplicate submits do not re-bill) and a per-request `MAX_OUTPUT_TOKENS` cap.
  *Accept:* replaying a request with the same idempotency key returns the prior
  result without a new model call; output cannot exceed the cap.
- **REQ-AID-106 — Human gate on issuance (HITL #1).** No AI-drafted solicitation
  is *issued* without explicit CO review and approval. The gate decision is
  classified by reversibility × blast-radius and recorded.
  *Accept:* an unreviewed draft cannot transition to "issued"; the approval
  writes an audit record (see REQ-X-402).

### M2 — Grounded retrieval (RAG)

- **REQ-RAG-201 — Corpus ingestion.** The FAR + DFARS corpus is ingested into
  Atlas Vector Search with per-chunk metadata: `corpus_source`, clause/section
  identifier, `last_revised`, `agency_id`.
  *Accept:* both FAR and DFARS parts are retrievable; ingestion does not silently
  drop parts (regression-tested).
- **REQ-RAG-202 — Hybrid clause search.** `POST /rag/clause-search` performs
  hybrid (dense + sparse) retrieval with rank fusion over the clause library.
  *Accept:* relevant clauses are returned within the latency budget (see
  REQ-X-404); the unused `pinecone-client` dependency is removed *(closes Item 7)*.
- **REQ-RAG-203 — Citations on every answer.** Every retrieved answer carries
  source citations (chunk/clause id + `corpus_source` + `last_revised`); answers
  with no supporting citation are not emitted as authoritative.
  *Accept:* a Q&A response without at least one resolvable citation is blocked or
  flagged for review.
- **REQ-RAG-204 — Multi-tenant retrieval boundary.** Retrieval is pre-filtered by
  `agency_id` resolved from request context; Agency A can never retrieve Agency
  B's content. *(Closes debt Item 10 at the retrieval layer.)*
  *Accept:* a cross-tenant retrieval test fails before this requirement and
  passes after; the test stays green in CI.
- **REQ-RAG-205 — Grounded vendor Q&A.** `POST /answer-qa` answers vendor
  questions strictly from retrieved corpus content with citations.
  *Accept:* answers are traceable to corpus chunks; no answer is fabricated from
  parametric knowledge alone.
- **REQ-RAG-206 — Faithfulness gate + human escalation (HITL #2).** A
  faithfulness/relevance judge (LLM-as-judge, threshold ≈0.85) gates answers;
  below threshold, the response is wrapped in a `needs_human_review` envelope and
  routed to a CO review queue rather than returned to the vendor.
  *Accept:* a known wrong-chunk case (high faithfulness, wrong evidence) is caught
  and escalated, not shipped.
- **REQ-RAG-207 — Evaluation harness as a gate.** A RAG eval harness runs in CI;
  a faithfulness regression beyond a set threshold (e.g. >5%) blocks the PR.
  *(Partially closes Item 12 — establishes the first real CI quality gate.)*
  *Accept:* a PR that improves latency but regresses faithfulness is blocked by
  the harness.
- **REQ-RAG-208 — LangChain v1.0 conformance.** All AI-orchestrator flows use
  LangChain v1.0 patterns; legacy `LLMChain(...).run(...)` and `legacy_chain.py`
  are removed. *(Closes debt Item 5.)*
  *Accept:* no `LLMChain`/`.run()` remains; flows compose via plain invoke +
  `create_agent`.

### M3 — Agentic source-selection workflow

- **REQ-AGT-301 — Single-agent intake triage.** `POST /agent/intake-triage` runs a
  ReAct loop that triages an incoming proposal/amendment situation, calling the
  M2 retrieval as a tool. State-mutating tools are idempotent; the run emits a
  LangSmith trace.
  *Accept:* a stale-amendment scenario is correctly detected on deterministic
  signals; replaying the same input does not double-write state.
- **REQ-AGT-302 — Multi-agent evaluation scaffolding + soft gate (HITL #4).** A
  supervisor-worker topology coordinates parallel evaluators; a **soft interrupt**
  at the supervisor→worker handoff gives the SSA visibility into supervisor
  decisions before consensus.
  *Accept:* the supervisor's routing decision is inspectable before workers run.
- **REQ-AGT-303 — Evaluation state machine.** The full
  `evaluator → consensus → ssa_review_ssdd → record_award` flow is a LangGraph
  state machine over `EvaluationState` (§9).
  *Accept:* the graph runs end to end on a synthetic evaluation and produces an
  SSDD draft + a (gated) award-record step.
- **REQ-AGT-304 — Hard human gates on reserved/irreversible steps (HITL #5).**
  `interrupt_before` halts the graph at `ssa_review_ssdd` (FAR 15.308 — SSA
  decision is non-delegable) and at `record_award` (FAR 5.705 — award publication
  is irreversible). The graph cannot pass these nodes without a human action.
  *Accept:* there is no code path that auto-approves either node; an attempt to
  do so is rejected.
- **REQ-AGT-305 — Durable checkpointing across the human gap.** `PostgresSaver`
  persists graph state so a run survives a multi-hour (or multi-day) SSA approval
  gap and resumes exactly where it paused; thread key = `agency_id:evaluation_id`.
  *Accept:* the process can be restarted between interrupt and resume with no
  state loss and no regeneration of already-reviewed content.
- **REQ-AGT-306 — FAR-cited audit on every gate transition.** Each
  interrupt/resume writes an append-only `AuditEvent` with `actor_id`,
  before/after state snapshot, governing FAR citation, and `correlation_id`.
  *Accept:* an OIG reviewer can reconstruct, from audit rows alone, who approved
  the SSDD and the award and under which authority.
- **REQ-AGT-307 — HITL boundary decision record (HITL #3).** Before building M3,
  every workflow transition is classified (no-gate / soft-gate / hard-gate) with
  its FAR citation and implementation primitive, recorded as an ADR.
  *Accept:* the gate map exists and each hard gate names its statute and uses
  `interrupt_before`.
- **REQ-AGT-308 — Single audit-writer.** Multi-agent runs write audit events
  through a single writer with a threaded `correlation_id`, avoiding per-agent
  fan-out races. *(Surfaces Item 2 + partially addresses Item 6; full fixes are
  Phase 2.)*
  *Accept:* a multi-agent run produces one coherent, correlation-threaded audit
  sequence, not N racing writes.
- **REQ-AGT-309 — Knowledge-graph view of the acquisitions schema.** The
  17-entity acquisitions model (§9) is represented for CO graph-traversal queries
  (e.g. "every contract this vendor won with red CPARs"), meeting <200ms p95 at
  the documented data volumes.
  *Accept:* the three canonical CO traversals (§9) return within budget; the
  datastore choice is justified in an ADR against the FedRAMP control cost of
  adding a third datastore.

## 8. Cross-cutting requirements

- **REQ-X-401 — HITL authority model.** Every state transition that an AI flow can
  reach is classified by **reversibility × blast-radius**. Statutorily reserved
  decisions (FAR 15.308 SSA) and irreversible actions (FAR 5.705 award; FAR
  15.206 amendment issuance) are **hard** gates regardless of model confidence.
  *"Accuracy is not the question; authority is."* Model confidence never
  downgrades a hard gate to a soft one.
- **REQ-X-402 — Append-only audit trail.** Audit records are append-only,
  modeled to FedRAMP AU-2 and OIG audit-finding expectations. No audit row is
  ever updated or deleted; corrections are new rows. (The legacy audit-log race,
  Item 2, is *surfaced* here and fully fixed in Phase 2.)
- **REQ-X-403 — Correlation across services.** AI-assisted requests thread a
  correlation/trace id across the services they touch. Phase 1 establishes the
  thread on the AI path (`ai-orchestrator` previously logged none); full W3C
  `traceparent` propagation across all four services is Phase 2 (Item 6).
- **REQ-X-404 — Cost + latency observability.** Per-request token/cost accounting
  (REQ-AID-104) and per-node latency instrumentation (LangSmith) are in place;
  retrieval p95 and graph-traversal p95 are measured against budgets
  (retrieval ≈800ms p95; CO graph traversal <200ms p95).
- **REQ-X-405 — Security baseline.** Synthetic data only (no live PII/CUI). AWS
  Bedrock (FedRAMP High via GovCloud, per ADR-0002) is the sole LLM path; no
  direct third-party model API. OWASP-LLM awareness for indirect injection
  (LLM01) and vector-store leakage (LLM08) informs design; the hardening *fixes*
  (Items 1, 9) are Phase 2.
- **REQ-X-406 — Eval-as-gate discipline.** Quality is gated by automated
  evaluation, not by manual inspection. Faithfulness/relevance for RAG
  (REQ-RAG-207) and trace-verified behavior for agents are the acceptance basis,
  and evals run in CI.

## 9. Data model

`acquire-gov` models federal acquisitions as a **graph of 17 entities**, not a
tree. The canonical enumeration + per-tenant data volumes live in the external
`feature-inventory-target.md`; the working set reconstructable today:

**Core spine:**
`Vendor ↔ Proposal ↔ Evaluation ↔ Award ↔ ContractModification ↔ Cpar`

**Named sub-entities:** `Solicitation`, `Amendment`, `EvaluationScore`
(per-evaluator), `ConsensusRound`, `SSDD` (source-selection decision document),
`Contract`, `IGCE`, `QaspFinding`, `Evaluator`. (Full 17 enumerated in the
canonical file.)

**Edge semantics:** `vendor_submitted_proposal`, `evaluator_scored_proposal`,
`award_modified_by`, `vendor_holds_cpar` (`WON`, `GOT_CPAR`).

**Canonical CO traversals (drive REQ-AGT-309):**
1. `Vendor → Award → Contract → Cpar` filtered `rating=red` (3 hops).
2. `Vendor → Award → Contract → QaspFinding → Evaluator` via `EvaluationScore` (4 hops, back-reference).
3. `Award → SSDD → Evaluation → IGCE ↔ ContractModification` (recursive on modification chains).

**Indicative data volumes (per agency/tenant):** ~100 vendors, ~500 proposals,
~80 active contracts — small for a graph; informs the datastore-choice ADR.

**Agentic runtime state** (`EvaluationState`, LangGraph):
`proposal_ids`, `evaluator_scores`, `consensus_complete`, `ssdd_draft`,
`ssa_approval_status`, `audit_correlation_id`. Plus a
`proposal_amendment_acknowledgements` record and append-only `AuditEvent` rows.

## 10. Success metrics & Phase 1 exit criteria

Phase 1 is complete when M1–M3 are demonstrable end to end and the following hold.
The exit bar maps to five dimensions:

| Dimension | Exit criterion |
|-----------|----------------|
| **Agent-flow architecture** | The `evaluator → consensus → ssa_review_ssdd → record_award` graph runs end to end on synthetic data with durable checkpointing across the human gap (REQ-AGT-303/305). |
| **Federal-authority semantics** | Every hard gate names its governing FAR clause; no auto-approve path exists for FAR 15.308 / 5.705 / 15.206 steps (REQ-AGT-304, REQ-X-401). |
| **HITL appropriateness** | Gates are classified by reversibility × blast-radius; soft vs hard is justified, not blanket (REQ-AGT-307). No gate sprawl, no skipped reserved decision. |
| **Knowledge-graph integration** | The 17-entity model answers the three canonical CO traversals within p95 budget (REQ-AGT-309). |
| **Brownfield-debt acknowledgement** | Items closed in Phase 1 (4, 5, 7, 10) are verifiably closed; partially-addressed (6, 12) and surfaced-but-deferred (2, 3) items are documented with a Phase 2 disposition. |

Supporting product metrics:
- Solicitation draft turnaround: weeks → minutes for a first reviewable draft.
- Grounding: 100% of authoritative Q&A answers carry a resolvable citation;
  below-threshold answers are escalated, not shipped (target: 0 ungrounded
  authoritative answers in eval).
- Auditability: 100% of hard-gate transitions produce a FAR-cited audit row.

## 11. Known unknowns / open questions

Standing backlog — resolved as the engagement deepens; each resolution lands in
the change log.

- **OQ-1** Exact `SolicitationDraft` schema fields beyond the known required set —
  refine with the CO's real solicitation template.
- **OQ-2** Faithfulness threshold (0.85 placeholder) — calibrate against a labeled
  eval set; may differ for clause-text vs. narrative content.
- **OQ-3** Knowledge-graph datastore — Neo4j vs. Postgres recursive CTE vs.
  in-process graph. Decision pending the FedRAMP control-surface trade-off ADR
  (REQ-AGT-309).
- **OQ-4** Hybrid-retrieval reranker — whether a dedicated reranker is needed to
  hit the latency + relevance budget, or RRF alone suffices.
- **OQ-5** Drafting UX — synchronous vs. streaming (SSE) delivery for
  `/draft-solicitation`; trades CO "watch it type" expectation against atomic
  delivery to the integration layer.
- **OQ-6** Embedding model + dimensionality for the clause corpus.
- **OQ-7** How much correlation-ID threading is in scope for Phase 1 vs. deferred
  to the Phase 2 OTel rollout (boundary of REQ-X-403).

## 12. Phase 2 outline (modernization — refined during Phase 1 close-out)

Phase 2 (modernization + operationalization) is sketched here so Phase 1
decisions don't paint it into a corner. **Outline only — specifics are
deliberately deferred** until the Phase 1 close-out review surfaces what the
adoption work actually revealed about the platform.

- **Brownfield modernization.** Spring Boot 2.7.18 → 4.0.x, Java 11 → 21,
  `javax.*` → `jakarta.*`, AWS SDK for Java v1 → v2 (v1 is end-of-support). Driven
  via OpenRewrite; strangler-fig where needed. Frontend stays on Angular 17.
- **AI security engineering.** Close Items 1 (JWT signature-skip / OWASP LLM07/08),
  9 (input sanitization / prompt-injection-via-stored-content, LLM01), 11
  (`:latest` images / supply chain, LLM03). Multi-tenant boundary extended beyond
  retrieval (Item 10 → full isolation).
- **Reliability + AIOps.** Item 3 (Resilience4j circuit breakers/timeouts on
  inter-service calls), Item 2 (audit-log race — transactional outbox), Item 6
  (consistent W3C `traceparent` + OpenTelemetry across all four services),
  AIOps platform + incident drill.
- **Resilience under load (mid-sprint surprise).** A production-incident response
  exercise on the evaluation→award workflow under load (the place where Items 2
  and 3 bite together). Stop-the-bleeding-before-root-cause discipline;
  spec-amend the plan with discovered behavior.
- **Client deliverability.** Runbook, ADR catalog, eval report, security
  attestation, HITL authority-boundaries doc, handoff.

A dedicated Phase 2 PRD will supersede this section once Phase 1 closes.

## 13. Change log

| Date | Change | Driver |
|------|--------|--------|
| 2026-05-28 | Initial Phase 1 PRD disseminated from sponsor objective. | Phase 1 kickoff |
