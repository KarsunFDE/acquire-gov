# Synthetic Solicitation Corpus Manifest

snapshot_date: 2026-06-09
generator: build_synthetic_solicitations.py @ uncommitted

**Synthetic data only.** All program names, dollar values, and office references are fictional. NAICS codes are real public taxonomy entries. No real CO identities, no real solicitation numbers from SAM.gov. See `docs/specs/m2-synthetic-corpus.md` section 6 for the data-class contract.

**Sections L/M intentionally absent** — Parts III/IV are out of lean scope per ADR-0005 D4. Wizard AI-draft for Sections L (Instructions to Offerors) and M (Evaluation Factors) will surface lower confidence at retrieval time; Phase 1.5 corpus expansion to Parts III/IV is the unblock path.

| File | Agency | Notice | Contract | Set-aside | Chunks (est.) |
|---|---|---|---|---|---|
| gsa-fas/SOL-GSA-001-cloud-managed-svcs.md | GSA-FAS | RFP | BPA | Small Business | 18 |
| gsa-fas/SOL-GSA-002-data-analytics-bpa.md | GSA-FAS | RFQ | IDIQ | 8(a) | 14 |
| gsa-fas/SOL-GSA-003-financial-erp-rfq.md | GSA-FAS | RFQ | FFP | Full-and-Open | 10 |
| gsa-fas/SOL-GSA-004-hr-modernization-rfp.md | GSA-FAS | RFP | CPFF | SDVOSB | 20 |
| gsa-fas/SOL-GSA-005-cybersecurity-iqid.md | GSA-FAS | RFI | IDIQ | Small Business | 12 |
| dod-dla/SOL-DOD-001-logistics-platform.md | DoD-DLA | RFP | FFP | Full-and-Open | 16 |
| dod-dla/SOL-DOD-002-medical-supply-rfp.md | DoD-DLA | RFP | FFP | Small Business | 12 |
| dod-dla/SOL-DOD-003-fuel-distribution-rfq.md | DoD-DLA | RFQ | FFP | 8(a) | 8 |
| dod-dla/SOL-DOD-004-spare-parts-iqid.md | DoD-DLA | RFI | IDIQ | SDVOSB | 10 |
| dod-dla/SOL-DOD-005-readiness-modeling.md | DoD-DLA | RFP | CPFF | Small Business | 18 |
