# FAR Snapshot Manifest

snapshot_date: 2026-06-09
source_urls:
  - https://www.acquisition.gov/far/part-15
  - https://www.acquisition.gov/far/part-52

**Public-domain regulation text.** FAR (Federal Acquisition Regulation) is a published federal regulation in the public domain; snapshots stored here are verbatim or close-paraphrase extracts used as the grounding corpus for the M2 retrieval pipeline. Lean-scope per ADR-0005 D4: Parts I + II only; Parts III/IV expansion deferred to Phase 1.5 (see `docs/specs/m2-retrieval-pipeline.md` §13).

Header convention per ADR-0006 D1: `#` = Part, `##` = Section, `###` = subsection.

| File | Part | Subparts covered |
|---|---|---|
| far-part-15.md | Part 15 — Contracting by Negotiation | Subpart 15.2 (15.200–15.210) |
| far-part-52.md | Part 52 — Solicitation Provisions and Contract Clauses | 52.100–52.107 (subpart 52.1); 52.212-* commercial-items family; 52.215-* negotiation provisions; 52.222-1, 52.232-1, 52.233-1, 52.246-1, 52.249-1 |

## Provenance + completeness notes

- `far-part-15.md` Subpart 15.2 was fetched live from `https://www.acquisition.gov/far/part-15` on the snapshot_date.
- `far-part-52.md` includes verbatim `52.212-4` text fetched from `https://www.acquisition.gov/far/52.212-4`; remaining 52.x clauses are present as title + statutory-reference stubs (lean-scope, sufficient for M2 retrieval test coverage). Full clause-text expansion to all 52.x is Phase 1.5 corpus work.

## Verification

Run `.github/scripts/verify-far-snapshot-manifest.sh` to recompute SHA-256 of each `.md` file in this directory and compare against `MANIFEST.sha256`. Mismatch exits 1.
