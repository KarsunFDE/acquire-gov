# FAR Snapshot Manifest

snapshot_date: 2026-06-09
source_urls:
  - https://www.acquisition.gov/far/part-15
  - https://www.acquisition.gov/far/part-52

**Public-domain regulation text.** FAR (Federal Acquisition Regulation) is a published federal regulation in the public domain; snapshots stored here are verbatim or close-paraphrase extracts used as the grounding corpus for the M2 retrieval pipeline. Lean-scope per ADR-0005 D4: Parts I + II only; Parts III/IV expansion deferred to Phase 1.5 (see `docs/specs/m2-grounded-retrieval/retrieval-pipeline.md` §13).

Header convention per ADR-0006 D1: `#` = Part, `##` = Section, `###` = subsection.

| File | Part | Subparts covered |
|---|---|---|
| far-part-15.md | Part 15 — Contracting by Negotiation | Subpart 15.2 (15.200–15.210) |
| far-part-52.md | Part 52 — Solicitation Provisions and Contract Clauses | 52.100–52.107 (subpart 52.1); 52.212-* commercial-items family; 52.215-* negotiation provisions; 52.222-1, 52.232-1, 52.233-1, 52.246-1, 52.249-1 |
| clause_applicability.json | Part II (Section I) clause-applicability matrix (ADR-0014 D3) | base clauses + per-set-aside (52.219-x family) + per-contract-type (52.216-x / 52.232-x / 52.246-1 / 52.249-1) + agency-supplement (GSAM 552.212-4, DFARS 252.204-7012) |

## Provenance + completeness notes

- `far-part-15.md` Subpart 15.2 was fetched live from `https://www.acquisition.gov/far/part-15` on the snapshot_date.
- `far-part-52.md` includes verbatim `52.212-4` text fetched from `https://www.acquisition.gov/far/52.212-4`; remaining 52.x clauses are present as title + statutory-reference stubs (lean-scope, sufficient for M2 retrieval test coverage). Full clause-text expansion to all 52.x is Phase 1.5 corpus work.

## clause_applicability.json sourcing notes

Derived from the FAR Part 52 prescription column (and FAR Part 19 set-aside prescriptions) as of the snapshot_date; agency-supplement rows reference GSAM 512.301 and DFARS 204.7304(c). Used by `app/agents/coordinator/part_ii.py::resolve_part_ii_clauses` for the deterministic (no-LLM) Part II resolution per ADR-0014 D3. Lean-scope: only the set-asides + contract types the trainer wizard offers; expansion is Phase 1.5 corpus work. Set-aside alias map (wizard enum → FAR spelling) lives in the file's `_meta.set_aside_aliases`.

## Verification

Run `.github/scripts/verify-far-snapshot-manifest.sh` to recompute SHA-256 of each `.md` file in this directory and compare against `MANIFEST.sha256`. Mismatch exits 1.
