# M2 Synthetic Corpus + Admin Ingest Pipeline — Implementation Spec

**Phase 1 · Milestone M2** · Sibling of [`docs/specs/m2-grounded-retrieval/retrieval-pipeline.md`](./retrieval-pipeline.md) and [`docs/specs/m2-grounded-retrieval/rollout.md`](./rollout.md). No new decisions; every claim cites the locking ADR section or re-states a contract from `m2-grounded-retrieval/retrieval-pipeline.md`.

## 1. Purpose

This spec owns two scopes. **First**, the lean synthetic solicitation corpus (10 docs × 2 agencies × FAR Parts I+II) — schema, generation procedure, on-disk layout, synthetic-safety contract per PRD §7 and ADR-0008 D1. **Second**, the admin-side ingest pipeline internals — format adapters (Markdown, plain text, PDF, JSON-prechunked), content-scan gate, audit-log writes, and the body of the `POST /ingest/document` handler. The endpoint's wire shape is locked in [`m2-grounded-retrieval/retrieval-pipeline.md` §4](./retrieval-pipeline.md); this spec details only the internals behind that contract.

## 2. Inputs from other specs

The endpoint shape and chunk schema below are **re-stated, not redefined**. Modifying either requires an ADR amendment, not a change to this spec.

```
POST /ingest/document
  Headers:
    X-Tenant-ID: <str>   (required; tenant_id stamped on every chunk for REQ-RAG-3)
    X-Request-ID: <uuid> (optional)
  Form data:
    file: bytes (<=10MB; >10MB → 413 payload_too_large)
    metadata: JSON string {
      "source_doc_name": str (required),
      "far_part":      str (optional — I|II|III|IV),
      "far_section":   str (optional — A-M),
      "snapshot_date": str (ISO date, required),
      "doc_class":     "far_reference"|"synthetic_solicitation"|"agency_template"
    }
    format: "md"|"txt"|"pdf"|"json-prechunked"
  Response 200:
    {"document_id": str, "chunks_inserted": int, "flagged_chunks": [], "duration_ms": int}
  Response 422 (ADR-0011 D1.1):
    {"error": "chunk_quality_flag_raised", "flagged_chunk_ids": [...]}
  Response 413: payload_too_large

CHUNK SCHEMA (ADR-0006 D2 — authoritative; do not redefine):
  {
    "_id": ObjectId,
    "tenant_id": str,           # REQ-RAG-3 filter
    "text": str,
    "embedding": [512 floats],  # Titan v2 @ 512
    "far_part": str,            # I|II|III|IV
    "far_section": str,         # A-M
    "far_subsection": str|null,
    "far_clause": str|null,     # e.g., "52.212-4"
    "subpart": str|null,
    "title": str,
    "source_doc": str,
    "snapshot_date": ISODate,
    "chunk_index": int,
    "char_start": int,
    "char_end": int,
    "doc_class": "far_reference"|"synthetic_solicitation"|"agency_template",
    "chunk_quality_flag": str|null    # ADR-0011 D1.1
  }
```

## 3. Lean corpus shape

| Item | Value |
|---|---|
| Total synthetic solicitation docs | 10 |
| Agencies | 2 (GSA-FAS, DoD-DLA) |
| FAR Parts covered | I (Sections A–H) + II (clauses via FAR Part 52) |
| Notice types mixed | RFP × 5, RFQ × 3, RFI × 2 |
| Contract types mixed | FFP × 4, IDIQ × 3, CPFF × 2, BPA × 1 |
| Set-asides mixed | Small Business × 4, 8(a) × 2, SDVOSB × 2, Full-and-Open × 2 |
| Doc size target | 8–20 chunks each (1200-char chunks) → ~10–30K chars per solicitation |
| Total chunks target | ~100–200 from synthetic solicitations + ~400–600 from FAR Part 15.2 + Part 52 snapshot |

**Sections L/M will be SPARSE in this corpus.** Parts III/IV are out of lean scope per ADR-0005 D4. Wizard AI-draft for L (Instructions to Offerors) and M (Evaluation Factors) will surface lower confidence at retrieval time — flag for `m2-grounded-retrieval/retrieval-pipeline.md` open-items and `m2-grounded-retrieval/eval-harness.md` threshold calibration. Phase 1.5 corpus expansion to Parts III/IV is the unblock path.

### 3.1 Per-doc generation matrix

The mix above is satisfied by the following deterministic assignment. The matrix is the input to the §7 generator config block.

| Doc | Agency | Notice | Contract | Set-aside | NAICS (synthetic) | Approx chunks |
|---|---|---|---|---|---|---|
| SOL-GSA-001 | GSA-FAS | RFP | BPA | Small Business | 541512 | 18 |
| SOL-GSA-002 | GSA-FAS | RFQ | IDIQ | 8(a) | 541511 | 14 |
| SOL-GSA-003 | GSA-FAS | RFQ | FFP | Full-and-Open | 518210 | 10 |
| SOL-GSA-004 | GSA-FAS | RFP | CPFF | SDVOSB | 541611 | 20 |
| SOL-GSA-005 | GSA-FAS | RFI | IDIQ | Small Business | 541519 | 12 |
| SOL-DOD-001 | DoD-DLA | RFP | FFP | Full-and-Open | 336411 | 16 |
| SOL-DOD-002 | DoD-DLA | RFP | BPA | Small Business | 339113 | 12 |
| SOL-DOD-003 | DoD-DLA | RFQ | FFP | 8(a) | 324110 | 8 |
| SOL-DOD-004 | DoD-DLA | RFI | IDIQ | SDVOSB | 332912 | 10 |
| SOL-DOD-005 | DoD-DLA | RFP | CPFF | Small Business | 541330 | 18 |

NAICS codes shown are real industry classifications (public taxonomy, not synthetic-restricted). All dollar values, program names, and offices in the generated prose are synthetic.

## 4. Two corpora, two paths

The `doc_class` field on every chunk lets retrieval and eval differentiate the corpora. Three distinct ingest paths, three distinct cadences.

| Corpus | doc_class | Lives in (repo) | Synthetic? | Ingest method | Re-ingest cadence |
|---|---|---|---|---|---|
| FAR snapshot (public regs) | `far_reference` | `docs/reference/far/` | No (public domain — ADR-0005 D5 carve-out) | Seed script (M2-02) | Manual; signed manifest (ADR-0011 D7) |
| Synthetic solicitations | `synthetic_solicitation` | `docs/reference/synthetic-solicitations/` | **YES** (PRD §7 mandate) | Seed script (M2-03 variant added by this spec) | On corpus change |
| Agency templates (admin upload) | `agency_template` | NOT checked in — runtime upload via `/ingest/document` | Synthetic-only at runtime; CI prefix check enforces | `/ingest/document` endpoint | Ad hoc |

## 5. Synthetic solicitation directory structure

```
docs/reference/synthetic-solicitations/
  MANIFEST.md                          # snapshot date + per-doc summary
  MANIFEST.sha256                      # SHA-256 per file (parallels FAR manifest pattern per ADR-0011 D7)
  gsa-fas/
    SOL-GSA-001-cloud-managed-svcs.md
    SOL-GSA-002-data-analytics-bpa.md
    SOL-GSA-003-financial-erp-rfq.md
    SOL-GSA-004-hr-modernization-rfp.md
    SOL-GSA-005-cybersecurity-iqid.md
  dod-dla/
    SOL-DOD-001-logistics-platform.md
    SOL-DOD-002-medical-supply-bpa.md
    SOL-DOD-003-fuel-distribution-rfq.md
    SOL-DOD-004-spare-parts-iqid.md
    SOL-DOD-005-readiness-modeling-sows.md
```

Each `.md` file mirrors the FAR markdown header convention from ADR-0006 D1 — the same `MarkdownHeaderTextSplitter` map applies, so the synthetic corpus parses through the exact same loader path as the FAR snapshot. No special-case logic.

```
# Solicitation SOL-GSA-001 — Cloud Managed Services BPA
## Section A — Solicitation/Contract Form
...
## Section B — Supplies/Services and Prices/Costs
...
## Section C — Statement of Work
### C.1 Scope
...
### C.2 Background
...
## Section D — Packaging and Marking
...
## Section E — Inspection and Acceptance
...
## Section F — Deliveries or Performance
...
## Section G — Contract Administration Data
...
## Section H — Special Contract Requirements
...
## Section I — Contract Clauses
### 52.212-4  Contract Terms and Conditions—Commercial Items
...
### 52.219-14  Limitations on Subcontracting
...
```

Sections L/M intentionally absent (Parts III/IV out of scope per ADR-0005 D4). Each section's content is **deliberately synthetic-flavored**: made-up agency program codes, fictional dollar values, generic NAICS codes — no real cleared-vendor names, no real solicitation numbers, no real CO identities.

### 5.1 MANIFEST.md shape

The manifest at `docs/reference/synthetic-solicitations/MANIFEST.md` is the human-readable index. The companion `MANIFEST.sha256` is the machine-verified integrity file (ADR-0011 D7).

```
# Synthetic Solicitation Corpus Manifest

snapshot_date: 2026-06-09
generator: build_synthetic_solicitations.py @ <git-sha>

| File | Agency | Notice | Contract | Set-aside | Chunks (est.) |
|---|---|---|---|---|---|
| gsa-fas/SOL-GSA-001-cloud-managed-svcs.md | GSA-FAS | RFP | BPA | Small Business | 18 |
| ... | ... | ... | ... | ... | ... |
```

`MANIFEST.sha256` format: one line per file, `<sha256>  <relative-path>`, identical to the FAR snapshot manifest pattern.

## 6. Synthetic-data safety contract

Per PRD §7 and ADR-0008 D1. **No exceptions.**

| Data class | Constraint | Source |
|---|---|---|
| Vendor data | SYNTHETIC ONLY | PRD §7 |
| Proposal data | SYNTHETIC ONLY | PRD §7 |
| Award data | SYNTHETIC ONLY | PRD §7 |
| CO identities | SYNTHETIC ONLY | PRD §7 |
| Solicitation prose | SYNTHETIC (no real SAM.gov copy even if public — names real procurement officials) | PRD §7, ADR-0008 D1 |
| FAR/DFARS text | REAL (public domain regulatory text) | ADR-0005 D5 carve-out |

**Enforcement.** `.github/workflows/synthetic-data-check.yml` enforces an allowlist of `source_doc_name` prefixes on every PR diff under `docs/reference/synthetic-solicitations/` and on every audit-log assertion in tests (per ADR-0008 D1, M2-01 ticket from `m2-grounded-retrieval/rollout.md`).

Acceptable prefixes:

| Prefix | Used by |
|---|---|
| `synthetic_*` | Generic synthetic fixtures |
| `SOL-GSA-*` | Synthetic GSA solicitations (this spec) |
| `SOL-DOD-*` | Synthetic DoD solicitations (this spec) |
| `FAR-*-snapshot` | FAR snapshot files (ADR-0005 D5) |
| `dfars-*` | DFARS snapshot files (ADR-0005 D5) |

Anything else under those paths fails CI on the PR. M2-01 must be extended with the `SOL-GSA-*` / `SOL-DOD-*` prefixes when ticket C14 lands.

## 7. Generation procedure

Script: `services/ai-orchestrator/seed/build_synthetic_solicitations.py`.

| Step | Behavior |
|---|---|
| 1 | Reads agency + NAICS + notice-type + contract-type + set-aside matrix from a config block at the top of the script. |
| 2 | For each of the 10 docs: emits a markdown file with Sections A–H + Section I (clause list drawn from the FAR Part 52 snapshot). |
| 3 | Uses templated boilerplate per section + synthetic specifics injected (program names from a curated synthetic-name list checked in alongside the script). |
| 4 | **Does NOT call an LLM at generation time.** Pure templating. Calling an LLM here would conflict with the eval ground-truth principle (anti-pattern #13, ADR-0009 D5) — the eval set treats these documents as authoritative answers, so they must be deterministic. |
| 5 | Runs once; outputs are checked into `docs/reference/synthetic-solicitations/` along with `MANIFEST.md` and `MANIFEST.sha256`. |
| 6 | Re-runs are idempotent — overwrites only on `--force` flag. Without `--force`, exits non-zero if any target file already exists. |

## 8. Ingest pipeline internals — POST /ingest/document body

The endpoint wire shape is locked in `m2-grounded-retrieval/retrieval-pipeline.md` §4. The handler internals are:

| # | Step | Detail | Lock |
|---|---|---|---|
| 1 | Rate-limit | slowapi per `X-Tenant-ID`; same limiter as `/retrieve` | ADR-0011 D4 |
| 2 | Auth check | admin role required | Open — admin-role enforcement is M1 territory; spec marks `Authorization: admin` header expected, full role check deferred |
| 3 | Parse multipart | `file` bytes, `metadata` JSON, `format` string | — |
| 4 | Size guard | `len(file) <= 10MB` else 413 `payload_too_large` | `m2-grounded-retrieval/retrieval-pipeline.md` §4 |
| 5 | Format adapter dispatch | `md`→`markdown.py` · `txt`→`plaintext.py` · `pdf`→`pdf.py` (pypdf) · `json-prechunked`→`json_prechunked.py` | §9 |
| 6 | Loader returns | `list[{text, far_part?, far_section?, far_subsection?, far_clause?, title?, char_start, char_end}]` | ADR-0006 D2 |
| 7 | Two-stage splitter | Per ADR-0006 D1. **SKIPPED if `format == "json-prechunked"`** — caller asserts chunks. | ADR-0006 D1 |
| 8 | Per-chunk content scan | `chunk_quality_flag` regex per ADR-0011 D1.1. If any chunk flagged: **ABORT**; return 422 with `flagged_chunk_ids`; **no insert** | ADR-0011 D1.1 |
| 9 | Embed chunks | `BedrockEmbeddings` Titan v2 @ 512 | ADR-0005 D2 |
| 10 | Bulk insert | Into `chunks` collection with full schema (tenant_id, doc_class, snapshot_date, source_doc, ...) | ADR-0006 D2 |
| 11 | Audit-log insert | `action="ingest_document"`, `outcome="ingested"`, `chunks_inserted`, `source_doc_name` | ADR-0008 D3 |
| 12 | Response | `200` with `document_id`, `chunks_inserted`, `flagged_chunks=[]`, `duration_ms` | `m2-grounded-retrieval/retrieval-pipeline.md` §4 |

Step 8 is the **fail-closed gate**: if any chunk trips the scan, the entire document is rejected. Partial ingest is not a behavior.

### 8.1 Audit-log record shape on successful ingest

Per ADR-0008 D3. The record below is what step 11 writes. Schema is the shared `audit_log` schema also used by `/retrieve` and `/draft-solicitation`; the `action` discriminator selects the meaningful payload fields.

```
{
  "_id": ObjectId,
  "ts": ISODate,
  "tenant_id": str,                     # from X-Tenant-ID header
  "request_id": str|null,               # from X-Request-ID header
  "action": "ingest_document",
  "outcome": "ingested",
  "actor_role": "admin",                # placeholder until M1 admin-role lands
  "source_doc_name": str,
  "doc_class": "far_reference"|"synthetic_solicitation"|"agency_template",
  "snapshot_date": ISODate,
  "format": "md"|"txt"|"pdf"|"json-prechunked",
  "chunks_inserted": int,
  "flagged_chunks": [],                 # always [] on success path; populated only on 422 outcome
  "duration_ms": int
}
```

Failure-outcome variants:

| `outcome` | `action` retained | Extra fields |
|---|---|---|
| `chunk_quality_flag_raised` | `ingest_document` | `flagged_chunk_ids: [...]`, `chunks_inserted: 0` |
| `duplicate_doc` | `ingest_document` | `existing_document_id: str`, `chunks_inserted: 0` |
| `payload_too_large` | `ingest_document` | `size_bytes: int`, `chunks_inserted: 0` |
| `pdf_text_extraction_failed` | `ingest_document` | `extracted_char_count: int`, `chunks_inserted: 0` |

All failure outcomes still write an audit record before responding. `outcome="rate_limited"` is the slowapi short-circuit case and does **not** audit (consistent with `m2-grounded-retrieval/retrieval-pipeline.md` §3 stage 1).

## 9. Format adapters — per-format detail

### 9.1 markdown.py

| Field | Value |
|---|---|
| Splitter | `langchain_text_splitters.MarkdownHeaderTextSplitter` (already in ADR-0006 D1) |
| Header map | `#` → `far_part` · `##` → `far_section` · `###` → `far_subsection` |
| `far_clause` extract | regex `\d{2}\.\d{3}(-\d+)?` on header text or first line of section |
| Output | Ordered chunks pre-second-stage-split (the splitter in §8 step 7 handles further breakdown) |

### 9.2 plaintext.py

| Field | Value |
|---|---|
| Splitter | Single-stage `RecursiveCharacterTextSplitter` only (no structural headers to detect) |
| Header metadata | All chunks get `far_part=null`, `far_section=null` **unless caller sets in metadata** — then applied to ALL chunks in the document |
| Retrieval quality | Lower than markdown for the same content; spec note. Plaintext is the escape hatch for unstructured uploads, not the preferred format |

### 9.3 pdf.py

| Field | Value |
|---|---|
| Library | `pypdf`. Escape hatch: `pdfplumber` if pypdf fails on cohort-provided PDFs |
| Extraction | Text per-page, concatenated with `\n\n` separators |
| Header heuristic | Lines matching `^Section [A-M] —` promoted to `##` markdown before passing to `MarkdownHeaderTextSplitter` (re-uses §9.1 path) |
| OCR | **Out of scope** for Phase 1. If extraction yields `< 100 chars total` → reject 422 with `error="pdf_text_extraction_failed"` |
| Image/table extraction | Out of scope (see §15) |

### 9.4 json_prechunked.py

Body shape:

```
{
  "chunks": [
    {"text": str, "metadata": {"far_part"?, "far_section"?, "far_subsection"?, "far_clause"?, "title"?}},
    ...
  ]
}
```

| Field | Value |
|---|---|
| Splitter | **Skipped** — caller has already chunked |
| Embedding | Still performed (no caller-provided embeddings accepted; eliminates dim/model mismatch risk) |
| Content scan | Still performed (ADR-0011 D1.1) |
| Use case | Migration from another system; admin paste of structured content |

## 10. Idempotency + duplicate-doc handling

| Scenario | Behavior |
|---|---|
| Re-ingest with same `source_doc` + same `snapshot_date` + same `tenant_id` | **REJECT 409 `duplicate_doc`**. Don't auto-replace; that's destructive. |
| Re-ingest with same `source_doc` + **later** `snapshot_date` | **ALLOWED.** New chunks coexist with the old; audit trail intact. Retrieval surfaces both unless caller passes `snapshot_date` filter. |
| Re-embed-with-new-dims | Not an update path. Per ADR-0007 D5: dual-write to a NEW field + flip. Treated as re-ingest under a separate index lifecycle. |

The `source_doc` field is the logical-document identity key. The `snapshot_date` is the version axis. Together they form the (tenant_id, source_doc, snapshot_date) uniqueness constraint enforced in application logic; no Mongo unique index because the chunks collection holds N chunks per document.

### 10.1 Pre-insert uniqueness probe

Step 10 of §8 expands as follows when the duplicate-doc check fires:

```
existing = chunks.find_one({
  "tenant_id": <header>,
  "source_doc": metadata.source_doc_name,
  "snapshot_date": metadata.snapshot_date
}, projection={"_id": 1})

if existing:
  audit_log.insert({..., outcome: "duplicate_doc", existing_document_id: existing._id, ...})
  return 409 {"error": "duplicate_doc", "existing_document_id": str(existing._id)}
```

The probe runs **after** the content scan succeeds, **before** the embed call. Rationale: embedding is the most expensive step (Bedrock Titan v2 token cost per ADR-0005 D2); we don't pay for embeddings on a duplicate.

## 11. Seed orchestration script

Script: `services/ai-orchestrator/seed/run_seed.py`. Single entry point that brings a fresh atlas-local container to a corpus-ready state.

| Step | Action |
|---|---|
| 1 | Ingest FAR snapshot (`doc_class=far_reference`). Reads `docs/reference/far/`. |
| 2 | Ingest 10 synthetic solicitations (`doc_class=synthetic_solicitation`). Reads `docs/reference/synthetic-solicitations/`. |
| 3 | Emit summary of `chunks_per_doc` + total embedding cost (token count × Titan v2 rate). |
| Idempotency | Skips if same `source_doc` + `snapshot_date` already in collection. Safe to re-run. |
| Invocation | Called from docker-compose entry script or `make seed` target. |

Run-seed shares the same loader stack as `/ingest/document` — it is the local-disk reader path against the same chunk-write code. No divergent code path; what the cohort runs at seed time is what admins run at endpoint time.

## 12. Inter-spec contracts

| Direction | Contract |
|---|---|
| **Provides** | Lean corpus seeded into atlas-local; `/ingest/document` endpoint behavior; `doc_class` field on every chunk; `MANIFEST.sha256` + synthetic-data CI prefix check |
| **Consumes** | Chunk schema (ADR-0006 D2); endpoint shape (`m2-grounded-retrieval/retrieval-pipeline.md` §4); Titan embedder (ADR-0005 D2); audit_log writer (ADR-0008 D3); content scan (ADR-0011 D1.1); FAR manifest pattern (ADR-0011 D7) |

## 13. Module + file layout

| Path | Owner |
|---|---|
| `services/ai-orchestrator/app/api/ingest.py` | FastAPI router for `/ingest/document` |
| `services/ai-orchestrator/app/ingest/loaders/markdown.py` | §9.1 |
| `services/ai-orchestrator/app/ingest/loaders/plaintext.py` | §9.2 |
| `services/ai-orchestrator/app/ingest/loaders/pdf.py` | §9.3 |
| `services/ai-orchestrator/app/ingest/loaders/json_prechunked.py` | §9.4 |
| `services/ai-orchestrator/app/ingest/scanner.py` | `chunk_quality_flag` regex per ADR-0011 D1.1 |
| `services/ai-orchestrator/seed/build_synthetic_solicitations.py` | §7 generator |
| `services/ai-orchestrator/seed/run_seed.py` | §11 orchestrator |
| `docs/reference/synthetic-solicitations/` | Checked-in lean corpus + `MANIFEST.md` + `MANIFEST.sha256` |
| `.github/workflows/synthetic-data-check.yml` | Extended with `SOL-GSA-*` + `SOL-DOD-*` prefixes per §6 |

## 14. PR integration with m2-grounded-retrieval/rollout.md

Three new tickets append to Slice C of `docs/specs/m2-grounded-retrieval/rollout.md`. Numbering picks up where the rollout spec stops (C11 is the last existing ticket).

| # | Branch | Title | Type | Depends on | Notes |
|---|---|---|---|---|---|
| **C12** | `cj/m2-c12-ingest-endpoint-and-loaders` | `POST /ingest/document` router + markdown/txt loaders | `feat(ingest):` | C9 (retrieve endpoint shape — same FastAPI wiring conventions) | Excludes PDF + JSON-prechunked to keep diff reviewable |
| **C13** | `cj/m2-c13-pdf-json-loaders` | PDF + JSON-prechunked loaders | `feat(ingest):` | C12 | Separate PR because PDF parsing is the most-likely-to-break adapter; adds `pypdf` dependency |
| **C14** | `cj/m2-c14-synthetic-solicitations` | Generate + check in 10 synthetic docs + MANIFEST | `feat(corpus):` | C2 (chunking) + C3 (embeddings) + C12 (loader stack) | Extends `synthetic-data-check.yml` allowlist with `SOL-GSA-*` + `SOL-DOD-*` |

## 15. Scope-out checklist

| Out | Why / when |
|---|---|
| OCR for scanned PDFs | Phase 1.5 |
| Image extraction / table extraction from PDF | Phase 1.5 |
| Real solicitation copy from SAM.gov even though public | Names real COs — synthetic-data constraint (ADR-0008 D1) |
| Live document fetch from external URL | Seed reads local snapshot only (ADR-0005 D5) |
| Multi-tenant per-tenant corpus isolation collections | Single `chunks` collection, `tenant_id` filter (ADR-0008 D2) |
| Cross-document deduplication via embedding similarity | Phase 1.5 |
| Encrypted-at-rest on atlas-local | Phase 1.5 cloud-Atlas migration (ADR-0008 D1) |
| Real PII detection on ingested content | Phase 1.5 (synthetic-only constraint absorbs the risk in Phase 1) |
| Versioned snapshot history beyond `snapshot_date` field | Phase 1.5 |
| Tenant registry | Phase 2 (CLAUDE.md) |
| Per-tenant ingest quota beyond rate-limit | Phase 1.5 |

## 16. Open items

| Item | Owner | Trigger |
|---|---|---|
| Admin-role enforcement on `/ingest/document` | M1 territory | Spec marks `Authorization: admin` header expected; full role check deferred to M1 auth work |
| Sections L/M sparse-corpus impact on AI-draft confidence | `m2-grounded-retrieval/retrieval-pipeline.md` open-items + `m2-grounded-retrieval/eval-harness.md` threshold calibration | Surface when eval harness lands; recalibrate withhold threshold if L/M draft confidence falls below `m2-grounded-retrieval/retrieval-pipeline.md` §3 stage-8 floor |
| Phase 1.5 Parts III/IV corpus expansion | Open — owned by ADR-XXXX | Separate PR + ADR if eval thresholds need recalibration when III/IV land |
| `pdfplumber` fallback decision | Open — owned by ADR-XXXX | If cohort PDFs fail pypdf extraction in C13 review |
