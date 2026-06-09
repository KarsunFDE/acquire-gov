"""Build the 10 synthetic solicitations under ``docs/reference/synthetic-solicitations/``.

Spec: ``docs/specs/m2-synthetic-corpus.md`` §3 (matrix) + §5 (layout) +
§7 (procedure).

**Pure templating, NO LLM calls** — anti-pattern #13 from ADR-0009 D5:
eval ground truth must not be LLM-generated against retrieval that uses
the same model family.

Synthetic-data safety (spec §6): fictional program codes, made-up dollar
values, NO real CO names, NO real solicitation numbers from SAM.gov. NAICS
codes are real (public taxonomy, not restricted by ADR-0008 D1).

Usage::

    python -m seed.build_synthetic_solicitations
    python -m seed.build_synthetic_solicitations --force   # overwrite existing
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import os
import sys
from pathlib import Path


# ---------- §3.1 generation matrix ----------

@dataclasses.dataclass(frozen=True)
class SpecRow:
    doc_id: str
    slug: str
    agency: str
    agency_dir: str  # "gsa-fas" | "dod-dla"
    notice: str
    contract: str
    set_aside: str
    naics: str
    program_name: str  # synthetic
    chunks_target: int


# Matrix locked in spec §3.1. Program names are synthetic.
MATRIX: list[SpecRow] = [
    SpecRow("SOL-GSA-001", "cloud-managed-svcs",   "GSA-FAS", "gsa-fas",
            "RFP", "BPA",  "Small Business",   "541512",
            "Synthetic Cloud Modernization Pathway (SCMP)", 18),
    SpecRow("SOL-GSA-002", "data-analytics-bpa",   "GSA-FAS", "gsa-fas",
            "RFQ", "IDIQ", "8(a)",             "541511",
            "Synthetic Analytics Pipeline Program (SAPP)", 14),
    SpecRow("SOL-GSA-003", "financial-erp-rfq",    "GSA-FAS", "gsa-fas",
            "RFQ", "FFP",  "Full-and-Open",    "518210",
            "Synthetic Finance ERP Refresh Initiative (SFERI)", 10),
    SpecRow("SOL-GSA-004", "hr-modernization-rfp", "GSA-FAS", "gsa-fas",
            "RFP", "CPFF", "SDVOSB",           "541611",
            "Synthetic HR Operations Transformation Program (SHOT)", 20),
    SpecRow("SOL-GSA-005", "cybersecurity-iqid",   "GSA-FAS", "gsa-fas",
            "RFI", "IDIQ", "Small Business",   "541519",
            "Synthetic Cyber Resilience Acquisition (SCRA)", 12),
    SpecRow("SOL-DOD-001", "logistics-platform",   "DoD-DLA", "dod-dla",
            "RFP", "FFP",  "Full-and-Open",    "336411",
            "Synthetic Defense Logistics Platform (SDLP)", 16),
    # Spec §3 summary table locks the mix at 4 FFP / 3 IDIQ / 2 CPFF / 1 BPA;
    # the §3.1 per-row matrix in the spec text had DOD-002 as BPA, which would
    # yield 3 FFP / 2 BPA. We honor the §3 summary (the agent-task mix
    # requirement was explicit) and update DOD-002 to FFP; the slug is
    # renamed accordingly so the filename matches the contract type.
    SpecRow("SOL-DOD-002", "medical-supply-rfp",   "DoD-DLA", "dod-dla",
            "RFP", "FFP",  "Small Business",   "339113",
            "Synthetic Defense Medical Supply Pipeline (SDMSP)", 12),
    SpecRow("SOL-DOD-003", "fuel-distribution-rfq","DoD-DLA", "dod-dla",
            "RFQ", "FFP",  "8(a)",             "324110",
            "Synthetic Fuel Distribution Initiative (SFDI)", 8),
    SpecRow("SOL-DOD-004", "spare-parts-iqid",     "DoD-DLA", "dod-dla",
            "RFI", "IDIQ", "SDVOSB",           "332912",
            "Synthetic Spare Parts Acquisition Vehicle (SSPAV)", 10),
    SpecRow("SOL-DOD-005", "readiness-modeling",   "DoD-DLA", "dod-dla",
            "RFP", "CPFF", "Small Business",   "541330",
            "Synthetic Readiness Modeling Engagement (SRME)", 18),
]


# ---------- §5 doc template ----------

# Section content is templated; per-section base prose multiplies up to the
# chunk-target via repetition with field interpolation. The result fits the
# 10–30 KB target band in spec §3 row 7.

_SECTION_A = """\
This solicitation is issued by the {agency} as a {notice} for the {program_name}
program under NAICS {naics}. The acquisition vehicle is {contract}; this
solicitation is set aside for {set_aside} concerns. All offers must be
submitted electronically through the agency portal by the closing date
indicated on the cover page. The Government intends to award without
discussions; however, the Contracting Officer reserves the right to conduct
discussions if determined to be in the Government's best interest under
FAR 15.306. This Section A captures the standard solicitation/contract form
elements per the Uniform Contract Format (UCF). Synthetic solicitation
identifier: {doc_id}. Reference date: {snapshot_date}.
"""

_SECTION_B = """\
Supplies and services required under this solicitation are described in
Section C. Pricing under {contract} shall be submitted in the offeror's
proposal as separately priced line items. For the {program_name}, estimated
quantities are notional and provided for planning purposes only; the
Government makes no commitment to order any minimum quantity beyond the
guaranteed minimum where applicable. Synthetic illustrative pricing reference:
contract ceiling estimated at $XX,000,000 across the period of performance.
Offerors shall propose firm-fixed unit prices, indefinite-quantity rate cards,
or cost-plus-fixed-fee arrangements consistent with the {contract} vehicle.
"""

_SECTION_C = """\
The Contractor shall perform the work described in this Statement of Work
(SOW) in support of the {program_name}. Tasks include strategy, design,
implementation, operations, and modernization activities tailored to the
{agency} mission. All work shall comply with applicable Federal Acquisition
Regulation (FAR) provisions and agency supplements. The Contractor shall
employ qualified personnel and apply industry-recognized practices for the
NAICS {naics} domain. Performance shall be measured against the metrics in
Section E (Inspection and Acceptance) and delivery schedule in Section F.
"""

_SECTION_C1 = """\
### C.1 Scope

The scope encompasses end-to-end services for the {program_name} including
requirements analysis, solution architecture, implementation, transition,
sustainment, and continuous improvement. Specific tasks are categorized by
work breakdown structure (WBS) elements detailed in the Performance Work
Statement (PWS) attachment.
"""

_SECTION_C2 = """\
### C.2 Background

The {agency} is undertaking the {program_name} to modernize and expand
mission-critical capabilities aligned with strategic priorities. Prior
analogous activities under NAICS {naics} have informed the requirements; this
acquisition consolidates lessons learned and applies them to a refreshed
operating model. Synthetic context only — no real predecessor contract is
referenced.
"""

_SECTION_D = """\
Packaging and marking shall conform to standard commercial practice unless
otherwise specified in the order. Deliverable products shall be marked with
the contract number, line item, and quantity. Electronic deliverables shall
follow the file-naming and metadata conventions in the PWS appendix. For
classified or controlled unclassified information (CUI) deliverables, see
Section H special contract requirements.
"""

_SECTION_E = """\
Inspection and acceptance of all deliverables shall occur at destination by
the designated Contracting Officer's Representative (COR). Acceptance
criteria include conformance with the SOW (Section C), schedule (Section F),
and the quality assurance surveillance plan (QASP) appended to the PWS. The
Contractor shall correct non-conforming deliverables at no cost within the
remediation period specified in the QASP. Quality metrics include on-time
delivery rate, defect density, customer satisfaction score, and security
control compliance evidence as applicable.
"""

_SECTION_F = """\
The period of performance is a base period plus option periods as specified
on the cover page. Deliveries or performance shall occur in accordance with
the schedule in the PWS. The Contractor shall notify the Contracting Officer
of any anticipated delay within five (5) business days of becoming aware of
the delay. FAR 52.212-4 applies to commercial items; otherwise FAR 52.249-8
or 52.249-9 (Termination) governs as appropriate.
"""

_SECTION_G = """\
Contract administration shall be performed by the assigned Contracting
Officer and COR. Invoices shall be submitted via the Wide Area Workflow
(WAWF) electronic platform or the agency-designated equivalent. Payment
terms follow the Prompt Payment Act (FAR 52.232-25). All contract
modifications shall be issued bilaterally via SF-30 under FAR 43.103 or
unilaterally where authorized.
"""

_SECTION_H = """\
Special contract requirements include but are not limited to: personnel
clearance requirements (where applicable), data rights treatment under
FAR 52.227-14, organizational conflict of interest (OCI) representations,
and section 508 accessibility compliance for any IT deliverables. For the
{set_aside} set-aside scope, the Contractor shall comply with the
applicable limitations on subcontracting per FAR 52.219-14. Synthetic
program details — fictional clearance level, fictional facility security
designations.
"""

# Section I clause list — clauses by ID only; full text comes from the FAR
# snapshot (doc_class=far_reference). This keeps the synthetic doc small
# and avoids duplicating regulatory text inside synthetic prose.
_SECTION_I_HEADER = """\
## Section I - Contract Clauses

The following Federal Acquisition Regulation (FAR) clauses are incorporated
by reference under FAR 52.252-2. Full clause text resides in the FAR snapshot
corpus (doc_class=far_reference); only clause IDs and titles appear here.
"""

# Per-contract-type clause selection. Each clause line is a level-### header
# so the markdown loader emits a far_clause-tagged chunk per spec §9.1.
_BASE_CLAUSES = [
    ("52.212-4",  "Contract Terms and Conditions - Commercial Items"),
    ("52.222-50", "Combating Trafficking in Persons"),
    ("52.232-25", "Prompt Payment"),
    ("52.232-33", "Payment by Electronic Funds Transfer - System for Award Management"),
    ("52.233-3",  "Protest After Award"),
    ("52.247-34", "F.O.B. Destination"),
]
_SET_ASIDE_CLAUSES = {
    "Small Business":  [("52.219-6",  "Notice of Total Small Business Set-Aside"),
                         ("52.219-14", "Limitations on Subcontracting")],
    "8(a)":            [("52.219-18", "Notification of Competition Limited to Eligible 8(a) Concerns"),
                         ("52.219-14", "Limitations on Subcontracting")],
    "SDVOSB":          [("52.219-27", "Notice of Service-Disabled Veteran-Owned Small Business Set-Aside"),
                         ("52.219-14", "Limitations on Subcontracting")],
    "Full-and-Open":   [("52.215-1",  "Instructions to Offerors - Competitive Acquisition")],
}
_CONTRACT_CLAUSES = {
    "FFP":  [("52.246-4",  "Inspection of Services - Fixed-Price")],
    "IDIQ": [("52.216-22", "Indefinite Quantity"),
             ("52.216-18", "Ordering")],
    "CPFF": [("52.216-7",  "Allowable Cost and Payment"),
             ("52.216-8",  "Fixed Fee")],
    "BPA":  [("13.303-2",  "Establishment of BPAs - Procedures"),
             ("13.303-5",  "Purchases under BPAs")],
}

_CLAUSE_BLOCK = """\
### {clause_id}  {clause_title}

Incorporated by reference per FAR 52.252-2. Refer to the FAR snapshot
(doc_class=far_reference) at snapshot_date={snapshot_date} for the
authoritative clause text.
"""


def _section_i(row: SpecRow, snapshot_date: str) -> str:
    seen: set[str] = set()
    blocks: list[str] = []
    for cid, title in (
        _BASE_CLAUSES
        + _SET_ASIDE_CLAUSES.get(row.set_aside, [])
        + _CONTRACT_CLAUSES.get(row.contract, [])
    ):
        if cid in seen:
            continue
        seen.add(cid)
        blocks.append(
            _CLAUSE_BLOCK.format(
                clause_id=cid, clause_title=title, snapshot_date=snapshot_date,
            )
        )
    return _SECTION_I_HEADER + "\n" + "\n".join(blocks)


def _expand_to_target_chunks(base_text: str, target_chunks: int) -> str:
    """Repeat ``base_text`` until char length reaches roughly
    ``target_chunks * 1200`` (CHUNK_SIZE from ADR-0006 D1). Conservative —
    we err on the long side so the second-stage splitter actually triggers.
    """
    target_chars = max(target_chunks, 1) * 1200
    out = base_text
    while len(out) < target_chars:
        out = out + "\n\n" + base_text
    return out


def build_document(row: SpecRow, snapshot_date: str) -> str:
    """Render the markdown body for one synthetic solicitation."""
    fmt = dict(
        doc_id=row.doc_id,
        slug=row.slug,
        agency=row.agency,
        notice=row.notice,
        contract=row.contract,
        set_aside=row.set_aside,
        naics=row.naics,
        program_name=row.program_name,
        snapshot_date=snapshot_date,
    )

    # Pad Section C with the C.1/C.2 subsections + repeat-expand prose so the
    # doc lands inside the 10–30 KB / 8–20-chunk band the spec calls for.
    section_c_full = (
        _SECTION_C.format(**fmt)
        + "\n"
        + _SECTION_C1.format(**fmt)
        + "\n"
        + _SECTION_C2.format(**fmt)
    )
    section_c_padded = _expand_to_target_chunks(section_c_full, row.chunks_target - 7)

    parts = [
        f"# Solicitation {row.doc_id} - {row.program_name}",
        "",
        f"## Section A - Solicitation/Contract Form",
        _SECTION_A.format(**fmt),
        f"## Section B - Supplies/Services and Prices/Costs",
        _SECTION_B.format(**fmt),
        f"## Section C - Statement of Work",
        section_c_padded,
        f"## Section D - Packaging and Marking",
        _SECTION_D.format(**fmt),
        f"## Section E - Inspection and Acceptance",
        _SECTION_E.format(**fmt),
        f"## Section F - Deliveries or Performance",
        _SECTION_F.format(**fmt),
        f"## Section G - Contract Administration Data",
        _SECTION_G.format(**fmt),
        f"## Section H - Special Contract Requirements",
        _SECTION_H.format(**fmt),
        _section_i(row, snapshot_date),
    ]
    return "\n".join(parts) + "\n"


# ---------- §5.1 manifest ----------

def build_manifest_md(rows: list[SpecRow], snapshot_date: str,
                       generator_sha: str) -> str:
    lines = [
        "# Synthetic Solicitation Corpus Manifest",
        "",
        f"snapshot_date: {snapshot_date}",
        f"generator: build_synthetic_solicitations.py @ {generator_sha}",
        "",
        "**Synthetic data only.** All program names, dollar values, and "
        "office references are fictional. NAICS codes are real public "
        "taxonomy entries. No real CO identities, no real solicitation "
        "numbers from SAM.gov. See `docs/specs/m2-synthetic-corpus.md` "
        "section 6 for the data-class contract.",
        "",
        "**Sections L/M intentionally absent** — Parts III/IV are out of "
        "lean scope per ADR-0005 D4. Wizard AI-draft for Sections L "
        "(Instructions to Offerors) and M (Evaluation Factors) will "
        "surface lower confidence at retrieval time; Phase 1.5 corpus "
        "expansion to Parts III/IV is the unblock path.",
        "",
        "| File | Agency | Notice | Contract | Set-aside | Chunks (est.) |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        rel = f"{r.agency_dir}/{r.doc_id}-{r.slug}.md"
        lines.append(
            f"| {rel} | {r.agency} | {r.notice} | {r.contract} | "
            f"{r.set_aside} | {r.chunks_target} |"
        )
    return "\n".join(lines) + "\n"


def build_sha256_manifest(files: list[tuple[str, bytes]]) -> str:
    """Return the ``MANIFEST.sha256`` content.

    Format: ``<sha256>  <relative-path>``, one line per file, sorted by
    path. Mirrors the FAR snapshot manifest pattern (ADR-0011 D7 / spec §5.1).
    """
    out: list[str] = []
    for path, content in sorted(files, key=lambda t: t[0]):
        digest = hashlib.sha256(content).hexdigest()
        out.append(f"{digest}  {path}")
    return "\n".join(out) + "\n"


# ---------- entry point ----------

def repo_root_corpus_dir() -> Path:
    here = Path(__file__).resolve()
    # services/ai-orchestrator/seed/this.py → repo root is parents[3]
    return here.parents[3] / "docs" / "reference" / "synthetic-solicitations"


def build_all(out_dir: Path, *, snapshot_date: str, force: bool,
              generator_sha: str = "uncommitted") -> dict[str, int]:
    """Render every doc + manifests into ``out_dir``.

    Returns a summary dict with counts. Idempotent: if a target file
    already exists and ``force`` is False, the script skips that file and
    counts it under ``skipped``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    file_records: list[tuple[str, bytes]] = []

    for row in MATRIX:
        sub = out_dir / row.agency_dir
        sub.mkdir(parents=True, exist_ok=True)
        rel = f"{row.agency_dir}/{row.doc_id}-{row.slug}.md"
        target = out_dir / row.agency_dir / f"{row.doc_id}-{row.slug}.md"
        body = build_document(row, snapshot_date)
        body_bytes = body.encode("utf-8")
        if target.exists() and not force:
            skipped += 1
            # Still hash the existing file for the manifest so MANIFEST.sha256
            # matches what's on disk.
            file_records.append((rel, target.read_bytes()))
            continue
        target.write_bytes(body_bytes)
        file_records.append((rel, body_bytes))
        written += 1

    manifest_md = build_manifest_md(MATRIX, snapshot_date, generator_sha)
    (out_dir / "MANIFEST.md").write_text(manifest_md, encoding="utf-8")

    sha_manifest = build_sha256_manifest(file_records)
    (out_dir / "MANIFEST.sha256").write_text(sha_manifest, encoding="utf-8")

    return {"written": written, "skipped": skipped, "total": len(MATRIX)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                         help="overwrite existing files")
    parser.add_argument("--snapshot-date", default="2026-06-09",
                         help="ISO snapshot date stamped on each doc + manifest")
    parser.add_argument("--out", default=None,
                         help="output directory (defaults to "
                              "docs/reference/synthetic-solicitations)")
    parser.add_argument("--generator-sha", default="uncommitted",
                         help="git SHA stamp for MANIFEST.md")
    args = parser.parse_args(argv)

    out_dir = Path(args.out) if args.out else repo_root_corpus_dir()
    summary = build_all(
        out_dir,
        snapshot_date=args.snapshot_date,
        force=args.force,
        generator_sha=args.generator_sha,
    )
    print(
        f"[build_synthetic_solicitations] wrote={summary['written']} "
        f"skipped={summary['skipped']} total={summary['total']} "
        f"into {out_dir}"
    )
    if summary["skipped"] and not args.force:
        print(
            "[build_synthetic_solicitations] tip: use --force to overwrite "
            "existing files.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
