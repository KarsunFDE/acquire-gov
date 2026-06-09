# M2 UI — FAR UCF Wizard + Grounding Surfaces Spec

**Phase 1 · Milestone M2** · Sibling of [`docs/specs/m2-retrieval-pipeline.md`](./m2-retrieval-pipeline.md), [`docs/specs/m2-eval-harness.md`](./m2-eval-harness.md), [`docs/specs/m2-synthetic-corpus.md`](./m2-synthetic-corpus.md). PR-ordered execution lives in [`docs/specs/m2-rollout.md`](./m2-rollout.md).

This spec owns the Angular UI surface for M2 grounded retrieval: wizard expansion onto the FAR 15.204-1 Uniform Contract Format, per-section provenance, HITL signals, and the admin ingest form. No new decisions; ambiguity is marked `Open — owned by ADR-XXXX` or deferred to an M3 spec.

## 1. Purpose

The Angular SPA is the cohort-facing surface for M2. M1 shipped a 5-step solicitation wizard that submitted raw, ungrounded Bedrock output (PRD §2 — the OIG-defensibility problem). M2 lands grounded retrieval, citation verification, and a soft/hard HITL gate (ADR-0007 D2, ADR-0008 D4, ADR-0011 D2). This spec breaks the wizard onto the full FAR UCF (Parts I–IV, Sections A–M; skip Section I = retrieved-only), surfaces grounding confidence + citations on every AI-drafted section, wires a publish/amend hard-gate modal citing FAR 5.705 / 15.206, and adds an admin ingest UI for the corpus.

Out of scope: backend pipeline (m2-retrieval-pipeline.md), eval harness (m2-eval-harness.md), corpus content (m2-synthetic-corpus.md), the LangGraph agent itself (M3), and solicitation-service Spring Boot work beyond the provenance entity shape this spec defines.

## 2. Inputs from other specs — LOCKED INTERFACES (do not redefine)

```
FROM m2-retrieval-pipeline.md:

POST /draft-solicitation/section
  Headers: X-Tenant-ID (required), X-Request-ID (UI generates uuid v4 client-side; passes through)
  Body: { section_id: "A".."M" (skip "I"), solicitation_id: str, query?: str, constraints?: str }
  Response 200:
    {
      "outcome": "draft_returned" | "hitl_pending" | "withheld" | "citation_verification_failed",
      "section_text": str | null,
      "section_id": str,
      "citations": [{"chunk_id", "text", "far_part", "far_section", "far_clause", "snapshot_date", "relevance_score"}],
      "gate_decision": "pass" | "hitl" | "withhold" | "rerank_unavailable_passthrough",
      "requires_human_review": bool,
      "rerank_top_score": float | null,
      "request_id": str
    }
  Response 403: {"error": "query_blocked", "reason": ...}
  Response 422: {"error": "citation_verification_failed", ...}
  Response 429: rate_limited
  Response 503: {"error": "bedrock_unavailable" | "mongo_unavailable", ...}

POST /ingest/document  (admin only)
  Form data: file, metadata (JSON string with source_doc_name, far_part?, far_section?, snapshot_date, doc_class),
             format: "md"|"txt"|"pdf"|"json-prechunked"
  Response 200: {"document_id", "chunks_inserted", "flagged_chunks": [], "duration_ms"}
  Response 422: {"error": "chunk_quality_flag_raised", "flagged_chunk_ids": [...]}
  Response 413: payload_too_large

PROVENANCE MODEL (owned by THIS spec but consumed by solicitation-service):
  Solicitation entity gains per-section fields:
    section_<X>_text: str
    section_<X>_provenance: "human" | "ai" | "ai-edited"
    section_<X>_ai_request_id: str | null   (correlates audit_log row)
    section_<X>_last_edited_at: timestamp
    section_<X>_last_edited_by: user_id
  Section transitions:
    null     → "human"     when CO types in an empty section
    null     → "ai"        when AI-drafts an empty section
    "human"  → "ai-edited" when CO clicks "AI-revise" on a human section
    "ai"     → "ai-edited" when CO edits any character of AI text
    "ai-edited" → "ai"     only on full re-draft (Reset + AI-Draft)
```

## 3. FAR UCF wizard step layout

Per FAR 15.204-1 ([acquisition.gov/far/15.204-1](https://www.acquisition.gov/far/15.204-1)) and ADR-0005 D4 mapping table. Section I is retrieved from FAR Part 52 (not drafted), so it splits into its own read-only step.

| Step | Title | Sections covered | Drafting mode | HITL gate | Source ADR / FAR |
|---|---|---|---|---|---|
| 1 | Basics | (none — metadata only: title, agency, NAICS, set-aside, contract type, notice type, ceiling, due date) | Human | None | — |
| 2 | Part I.A — Solicitation/Contract Form | A | Human (operator-entered per ADR-0005 D4) | None | ADR-0005 D4 |
| 3 | Part I.B — Supplies/Services + Prices | B | Human | None | ADR-0005 D4 |
| 4 | Part I.C — Statement of Work | C | AI-drafted (grounded); editable | Soft (rerank band) | ADR-0005 D4, ADR-0007 D2 |
| 5 | Part I.D–G — Packaging / Inspection / Delivery / Admin | D, E, F, G | Human | None | ADR-0005 D4 |
| 6 | Part I.H — Special Contract Requirements | H | AI-drafted (grounded); editable | Soft | ADR-0005 D4, ADR-0007 D2 |
| 7 | Part II.I — Contract Clauses | I (clauses retrieved from FAR Part 52) | Retrieved-only; no human edit on this list | None (read-only retrieval) | ADR-0005 D4 |
| 8 | Part III.J — Attachments | J | Human (file upload — file persistence is M3 storage open item) | None | ADR-0005 D4 |
| 9 | Part IV.K — Reps + Certs | K | Template-driven (human-edited; retrieval suggests template) | None | ADR-0005 D4 |
| 10 | Part IV.L — Instructions to Offerors | L | AI-drafted (grounded); editable. **Lean corpus has sparse L coverage** — expect higher `hitl` / `withhold` rate | Soft | ADR-0005 D4, m2-synthetic-corpus.md |
| 11 | Part IV.M — Evaluation Factors | M | AI-drafted (grounded); editable. **Lean corpus has sparse M coverage** — same caveat as L | Soft | ADR-0005 D4, m2-synthetic-corpus.md |
| 12 | Review + cross-section consistency | All | Auto-check (FAR 15.204-5: L instructions ↔ M factors) | Soft (warn if mismatch) | ADR-0005 D4 |
| 13 | Submit for internal review → ready-to-publish | All | — | **Hard gate**: publish disabled until INTERNAL_REVIEW → READY_TO_PUBLISH transition signed by CO | ADR-0008 D4, FAR 5.705 |

Section I split rationale: content is RETRIEVED from FAR Part 52 (not drafted); UI shows a resolved clause list, not an editable textarea. ADR-0005 D4.

## 4. Per-section UI shell

Every drafted section step (C, H, L, M) renders the same shell component (`section-card.component.ts`, §9).

```
┌─ Section <X> — <Title> ────────────────────────────────────────┐
│ Provenance: [ Human ] [ AI ] [ AI-edited ]   ← badge           │
│ Last edited: <user> at <ts>                                    │
│                                                                │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ <textarea — current section text>                        │   │
│ │                                                          │   │
│ └──────────────────────────────────────────────────────────┘   │
│                                                                │
│ [ AI-draft this section ]  [ Reset to empty ]                  │
│                                                                │
│ ─── If AI-drafted, additional UI ─────────────────────────────  │
│ Grounding confidence: ●●●○○  (rerank_top_score 0.62)           │
│ Status badge:  [ Grounded ✓ ] | [ ⚠ Needs CO review ] |         │
│                [ ⚠ Insufficient grounding — withheld ]          │
│                                                                │
│ Citations (top-5):                                             │
│   1. FAR Part IV § L.5    (snapshot 2026-06-01)   0.74          │
│      "Volume I shall not exceed 60 pages…"                     │
│      [ ▾ expand citation text ]                                │
│   2. FAR Part II § 52.215-1                       0.68          │
│   …                                                            │
│                                                                │
│ Audit-trail link: request_id <uuid>                            │
└────────────────────────────────────────────────────────────────┘
```

### 4.1 Badge classes + tokens

| Token | CSS class | Use |
|---|---|---|
| `provenance--human` | grey 600 | Human-authored badge |
| `provenance--ai` | blue 600 | AI-drafted badge |
| `provenance--ai-edited` | violet 600 | AI-edited badge |
| `gate--pass` | green 600 | "Grounded ✓" |
| `gate--hitl` | amber 600 | "⚠ Needs CO review" |
| `gate--withhold` | red 600 | "⚠ Insufficient grounding — withheld" |
| `gate--degraded` | orange 500 | "⚠ Degraded mode — review every citation" |

Classes live in `frontend/src/app/styles/_provenance.scss` (NEW).

### 4.2 Confidence-dot mapping

The `rerank_top_score` → `●●●○○` mapping is a pure function in `section-card.component.ts`:

| `rerank_top_score` range | Dots filled |
|---|---|
| `null` (degraded passthrough) | `○○○○○` |
| `< 0.40` | `●○○○○` |
| `0.40 – 0.55` | `●●○○○` |
| `0.55 – 0.70` | `●●●○○` |
| `0.70 – 0.85` | `●●●●○` |
| `≥ 0.85` | `●●●●●` |

Mapping is presentation-only; the authoritative gate decision is `gate_decision` from the backend (ADR-0007 D2). Dots never override the badge.

## 5. Provenance badge state machine

Per the LOCKED PROVENANCE MODEL (§2). All transitions are client-side; the PATCH body to `/solicitations/<id>` carries the new provenance value alongside the text.

| Trigger | From | To |
|---|---|---|
| User types in empty section | `null` | `human` |
| "AI-draft" returns `outcome: draft_returned` | `null` / `human` / `ai-edited` | `ai` (overwrite) |
| User edits ≥1 char of AI text | `ai` | `ai-edited` |
| "AI-revise" called on human-authored section | `human` | `ai-edited` |
| "Reset to empty" clicked | any | `null` |
| Full re-draft (Reset + AI-Draft) | `ai-edited` | `ai` |

State machine lives in `section-card.component.ts`; unit tests in §13.

Per-paragraph / per-sentence provenance is explicitly out of scope (§16) — Phase 1.5+ CRDT/Yjs class of work. Per-section is the locked granularity (user clarification).

## 6. HITL surfaces

Three classes. All cite the backend signal they consume.

### 6.1 Soft-gate (per-section) — rerank-band signal

Driven by `gate_decision` and `requires_human_review` from `/draft-solicitation/section` (ADR-0007 D2).

| Backend signal | Badge | Section behavior |
|---|---|---|
| `gate_decision: "pass"` | `[ Grounded ✓ ]` green | Text shown; Step 13 publish-readiness counts as clean |
| `gate_decision: "hitl"` OR `requires_human_review: true` | `[ ⚠ Needs CO review ]` amber | Section saves; Step 13 counts as non-clean until CO toggles "reviewed" checkbox on card |
| `gate_decision: "withhold"` | `[ ⚠ Insufficient grounding — withheld ]` red banner | `section_text` is null; CO must either type human content OR re-draft with refined query |
| `gate_decision: "rerank_unavailable_passthrough"` | `[ ⚠ Degraded mode — review every citation ]` orange | Citations shown without `relevance_score`; CO must explicitly toggle "reviewed" before Step 13 will pass |

### 6.2 Hard-gate (per-action) — publish + amend

Backend HITL middleware (ADR-0008 D4) is M3 wiring (`m2-rollout.md` M2-10/M2-11 deferred). Phase 1 UI surface is **client-side modal friction + solicitation-service state-machine**.

| Action | Trigger | Modal text requirement | Citation |
|---|---|---|---|
| Publish | Step 13 publish button | CO must type "I am the CO and approve" (case-insensitive) OR click checkbox carrying the same text | FAR 5.705 |
| Amend | Amendment editor save | Same friction; modal cites amendment rationale field as mandatory | FAR 15.206 |
| SSA decision (M3 forward-ref) | (placeholder) | Disabled stub button + tooltip: "M3 — agentic workflow approves; signs require CO present" | FAR 15.308 |
| Award (M3 forward-ref) | (placeholder) | Same disabled stub | FAR (M3 spec) |

The Phase 1 UI hard-gates DO NOT call into the agent HITL middleware (no agent wired). M3 swaps in the LangGraph interrupt flow (ADR-0008 D4) — the publish/amend modals stay, but Step 13 also waits on `interrupt`/`Command(resume=...)` round-trip.

### 6.3 Error-state HITL — 403 / 429 / 503

| Status | UI | Toast? |
|---|---|---|
| `403 query_blocked` (ADR-0011 D2) | Friendly inline error in section card: "Query rejected by content policy. Refine and retry." | No toast |
| `422 citation_verification_failed` (ADR-0011 D3) | Inline: "Draft generated but citations failed verification — text withheld." | No toast |
| `429 rate_limited` (ADR-0011 D4) | Inline: "Rate limited; try again shortly." Disable AI-draft button 10s. | No toast |
| `503 bedrock_unavailable` / `mongo_unavailable` | Inline: "Drafting service temporarily unavailable. Type the section manually or retry." | No toast |

No toast notifications anywhere — all errors are localized to the section card. ADR-0011 D2 / D4.

## 7. Audit-trail visibility

Every AI-drafted section card shows `request_id` as a clickable link. Link target: `/audit/<request_id>` route → reuses existing `audit-search.component`. ADR-0008 D3 (audit_log request_id correlation).

Audit-log read endpoint location (`GET /audit-log?request_id=...`) is **Open — owner TBD**. Reasonable default is ai-orchestrator with `auditLogReader` role binding, but cross-service auth not yet spec'd in Phase 1 (see §17).

## 8. Solicitation-service entity changes (consumer change — forward-reference)

This spec defines the SHAPE; the solicitation-service track owns the backend migration. Frontend model (`frontend/src/app/models/solicitation.ts`):

```typescript
export type SectionProvenance = 'human' | 'ai' | 'ai-edited' | null;

export interface SectionAudit {
  provenance: SectionProvenance;
  aiRequestId?: string | null;
  lastEditedAt?: string;
  lastEditedBy?: string;
  lastRerankTopScore?: number | null;
  lastGateDecision?: 'pass' | 'hitl' | 'withhold' | 'rerank_unavailable_passthrough' | null;
}

export interface SolicitationSections {
  sectionA?: string;   sectionAAudit?: SectionAudit;
  sectionB?: string;   sectionBAudit?: SectionAudit;
  sectionC?: string;   sectionCAudit?: SectionAudit;
  sectionD?: string;   sectionDAudit?: SectionAudit;
  sectionE?: string;   sectionEAudit?: SectionAudit;
  sectionF?: string;   sectionFAudit?: SectionAudit;
  sectionG?: string;   sectionGAudit?: SectionAudit;
  sectionH?: string;   sectionHAudit?: SectionAudit;
  sectionJ?: string;   sectionJAudit?: SectionAudit;
  sectionK?: string;   sectionKAudit?: SectionAudit;
  sectionL?: string;   sectionLAudit?: SectionAudit;
  sectionM?: string;   sectionMAudit?: SectionAudit;
}
```

Section I is intentionally absent — Section I content is retrieved-only (FAR Part 52 clause list), not edited or stored as section text. ADR-0005 D4.

Backend persistence is the **solicitation-service track** (Spring Boot 2.7.18 — JPA Postgres). Spec note: ADD columns in a new Flyway migration. Do NOT pre-do W4 SB 4.0.x / Java 21 modernization. Frontend dispatches PATCH against the existing `/solicitations/<id>` endpoint.

## 9. Component additions / changes

| Path | Change |
|---|---|
| `frontend/src/app/components/solicitation-wizard/solicitation-wizard.component.ts` | Expand from 5 steps to 13 steps. Per-section UI shell (§4). State machine (§5). |
| `frontend/src/app/components/solicitation-wizard/section-card.component.ts` | NEW — reusable per-section card (textarea + AI-draft button + provenance badge + citations + audit link). |
| `frontend/src/app/components/solicitation-wizard/citation-list.component.ts` | NEW — expandable citation row with chunk text. |
| `frontend/src/app/components/admin-ingest/admin-ingest.component.ts` | NEW — admin upload form (file + metadata + format select). |
| `frontend/src/app/models/solicitation.ts` | Expand `SolicitationSections` with `SectionAudit` per-section block. |
| `frontend/src/app/services/solicitation.service.ts` | Add `draftSection(id, sectionId, query?, constraints?)` calling POST /draft-solicitation/section. |
| `frontend/src/app/services/ingest.service.ts` | NEW — wraps POST /ingest/document. |
| `frontend/src/app/app.routes.ts` | Add `/admin/ingest` route guarded by admin role. |
| `frontend/src/app/shell/sidebar-nav.component.ts` | Add "Admin → Ingest" link for admin role. |
| `frontend/src/app/components/amendment-editor/amendment-editor.component.ts` | Add hard-gate publish modal (FAR 15.206). |
| `frontend/src/app/styles/_provenance.scss` | NEW — badge token classes (§4.1). |

## 10. Admin ingest UI

New route `/admin/ingest`, gated by admin role guard (§11). Wraps POST `/ingest/document` (§2 LOCKED INTERFACES). Consumes corpus availability from `m2-synthetic-corpus.md`.

```
/admin/ingest

┌─ Upload corpus document ─────────────────────────────────────┐
│ Tenant: [agency-test ▾]                                       │
│ Format: ( ) MD   ( ) TXT   ( ) PDF   ( ) JSON-prechunked      │
│ File:   [ Choose file… ]                                      │
│                                                               │
│ Metadata:                                                     │
│   Source doc name: [_________________]                        │
│   FAR part (opt):  [I|II|III|IV ▾]                            │
│   FAR section:     [A-M ▾]                                    │
│   Snapshot date:   [YYYY-MM-DD]                               │
│   Doc class:       (•) synthetic_solicitation                 │
│                    ( ) far_reference                          │
│                    ( ) agency_template                        │
│                                                               │
│ [ Upload ]                                                    │
│                                                               │
│ ─── Upload result ──────────────────────────────────────────── │
│ document_id: <uuid>                                           │
│ chunks_inserted: 42                                           │
│ flagged_chunks: 0                                             │
│ duration_ms: 1283                                             │
└───────────────────────────────────────────────────────────────┘
```

### 10.1 Inline error states

| Status | Inline message |
|---|---|
| `413 payload_too_large` | "File too large (10MB limit)." |
| `422 chunk_quality_flag_raised` | "Content flagged for review — see flagged_chunks list." (Renders `flagged_chunk_ids` list below.) |
| `429 rate_limited` | "Rate limited; try again shortly." |
| `503` | "Ingest service temporarily unavailable." |

### 10.2 Recent uploads list

Below the form, render the last 10 uploads for the current tenant, sourced from a new `GET /ingest/recent?tenant_id=...` endpoint. **Open — owner TBD; reasonable default is orchestrator alongside ingest.** See §17.

## 11. Role + access control

| Role | Wizard | Publish | Admin ingest |
|---|---|---|---|
| Specialist | edit | no | no |
| Contracting Officer (CO) | edit | yes (hard-gate modal §6.2) | no |
| Admin | edit | yes | yes |
| Reviewer | read | no | no |

Existing role guard (`frontend/src/app/services/role.guard.ts`) extends with `admin` for `/admin/ingest`.

**Spec NOTE:** Real role enforcement on the backend is M1 territory and ADR-0004 M9 (caller-asserted tenant_id pattern, hardened in M9). UI guard is presentation only; backend is assumed-enforced. This spec does not re-open ADR-0004 M9.

## 12. Lean-corpus reality surfaced in UI

Per `m2-synthetic-corpus.md`: initial corpus covers FAR Parts I+II well; Sections L and M (Part IV) have sparse coverage until Phase 1.5 expansion.

UI surface:
- Sections L and M AI-draft buttons display an info banner on first use per session:
  > "Note: grounding corpus currently covers FAR Parts I+II. Drafts for Section L/M may surface lower confidence until corpus expansion (Phase 1.5)."
- Banner dismissible via `localStorage` key `ui.lean-corpus-banner-dismissed:v1`.
- Banner does NOT block drafting — it warns. The actual confidence signal still comes from `gate_decision` (§6.1).

## 13. Test surface (component tests only)

This spec covers UI tests, not e2e. e2e for the end-to-end retrieval path lives in `m2-eval-harness.md`.

| Test | Component | Covers |
|---|---|---|
| Provenance transitions: all 6 rows of §5 table | `section-card.component.spec.ts` | §5 state machine |
| Badge rendering for each `gate_decision` value (4 cases) | `section-card.component.spec.ts` | §6.1 |
| Citation list expand/collapse | `citation-list.component.spec.ts` | §4 shell |
| Admin ingest form validation (file size, format required, metadata required) | `admin-ingest.component.spec.ts` | §10 |
| 4xx/5xx error surfaces (403, 422, 429, 503) | `section-card.component.spec.ts` + `admin-ingest.component.spec.ts` | §6.3, §10.1 |
| Hard-gate modal text-confirmation rejects empty / wrong text | `solicitation-wizard.component.spec.ts` | §6.2 |
| Lean-corpus banner shows once, dismissible via localStorage | `section-card.component.spec.ts` | §12 |

## 14. Inter-spec contracts

| Direction | What | Counterparty |
|---|---|---|
| Provides | Provenance shape (`SectionAudit` per-section block) | solicitation-service (consumes for Postgres migration) |
| Provides | Audit-trail link route `/audit/<request_id>` | audit endpoint owner (Open — §17) |
| Consumes | `/draft-solicitation/section` request + response shape | `m2-retrieval-pipeline.md` |
| Consumes | `/ingest/document` request + response shape | `m2-retrieval-pipeline.md` |
| Consumes | Corpus availability + Section L/M coverage caveat | `m2-synthetic-corpus.md` |

## 15. PR integration with `m2-rollout.md`

Three new tickets to add to Slice C (parallel-implementable once C9 `/retrieve` endpoint and C12 `/ingest/document` are live — the section-draft endpoint is the same orchestrator surface; ordering note in §15.1).

| # | Branch | Title | Type | Depends on |
|---|---|---|---|---|
| **C15** | `cj/m2-c15-wizard-far-ucf-expand` | Expand wizard to 13 steps; section-card + citation-list components; provenance state machine; consume `/draft-solicitation/section` | `feat(ui):` | C9 (orchestrator endpoint live) |
| **C16** | `cj/m2-c16-admin-ingest-ui` | admin-ingest component + `/admin/ingest` route + `ingest.service.ts` | `feat(ui):` | C2/C12 (ingest endpoint live) |
| **C17** | `cj/m2-c17-hard-gate-modals` | Publish + amend modals citing FAR 5.705 / 15.206; SSA/award disabled stubs (M3 forward-ref) | `feat(ui):` | none (pure client-side friction) |

### 15.1 Ordering note

C15, C16, C17 are parallel-implementable among themselves. C15 blocks on backend C9 (the section-draft endpoint shares orchestrator surface with `/retrieve`); C16 blocks on the ingest endpoint landing (C2 ingest scan + C12 endpoint exposure). C17 is pure client-side and can ship any time after the wizard exists.

## 16. Scope-out checklist

- [ ] Agentic workflow — M3 (wizard surfaces are placeholders; LangGraph interrupt flow lands later)
- [ ] Backend HITL middleware wiring — M3 (`m2-rollout.md` M2-10/M2-11 deferred)
- [ ] Real LangGraph agent in the section-draft path — Phase 1 hits `/draft-solicitation/section` directly
- [ ] Per-paragraph or per-sentence provenance — Phase 1.5+ (CRDT/Yjs class of work)
- [ ] Attachment file persistence (Section J) — Open; M3 / Phase 1.5 storage spec
- [ ] Multi-language UI — Phase 2
- [ ] Tenant registry / tenant-switcher beyond hardcoded dropdown — Phase 2
- [ ] Real-time streaming token render — Phase 1.5 (orchestrator returns full response, no SSE)
- [ ] Spring Boot solicitation-service migration to SB 4.0.x / Java 21 — W4 cohort work
- [ ] Backend column migration owned by solicitation-service track — this spec defines SHAPE only
- [ ] Output-side Guardrails (ADR-0011 D2) — Phase 1.5
- [ ] Audit-log read endpoint owner — Open (§17)
- [ ] Toast notification system — explicitly rejected; all errors inline (§6.3)

## 17. Open items

| Item | Why open | Reasonable default |
|---|---|---|
| Audit-log read endpoint location (`GET /audit-log?request_id=...`) | Cross-service auth for `auditLogReader` role not yet spec'd in Phase 1 | Orchestrator alongside audit_log writer (ADR-0008 D3); needs role-binding spec |
| Section J attachment storage backend | Phase 1 has no file persistence story | Defer to M3 or Phase 1.5 storage spec |
| Section M ↔ Section L cross-validation engine (FAR 15.204-5 alignment) | Structural check requires retrieval over both section texts | Step 12 warn-only Phase 1; structural check with M3 or a separate spec |
| `GET /ingest/recent?tenant_id=...` endpoint owner | Read-side counterpart to `/ingest/document`; not in m2-retrieval-pipeline.md LOCKED INTERFACES | Orchestrator alongside ingest writer; reuses tenant pre-filter from ADR-0008 D2 |

---

**End of spec.** No new decisions; every claim traces to ADR-0005..0011, FAR 15.204-1 / 5.705 / 15.206 / 15.308, or sibling spec. Open items §17 enumerate genuinely undecided surface; everything else is locked.
