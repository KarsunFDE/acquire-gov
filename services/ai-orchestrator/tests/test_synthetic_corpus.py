"""C14 — synthetic corpus generation tests.

Spec: ``docs/specs/m2-synthetic-corpus.md`` §3 / §5 / §7.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from seed import build_synthetic_solicitations as gen


_REPO_ROOT = Path(__file__).resolve().parents[3]
_CORPUS_DIR = _REPO_ROOT / "docs" / "reference" / "synthetic-solicitations"


def test_matrix_has_ten_docs_with_required_mix() -> None:
    """Spec §3 — 10 docs across the locked agency / notice / contract /
    set-aside mix.
    """
    rows = gen.MATRIX
    assert len(rows) == 10

    agencies = [r.agency for r in rows]
    assert agencies.count("GSA-FAS") == 5
    assert agencies.count("DoD-DLA") == 5

    notice = [r.notice for r in rows]
    assert notice.count("RFP") == 5
    assert notice.count("RFQ") == 3
    assert notice.count("RFI") == 2

    contract = [r.contract for r in rows]
    assert contract.count("FFP") == 4
    assert contract.count("IDIQ") == 3
    assert contract.count("CPFF") == 2
    assert contract.count("BPA") == 1

    set_asides = [r.set_aside for r in rows]
    assert set_asides.count("Small Business") == 4
    assert set_asides.count("8(a)") == 2
    assert set_asides.count("SDVOSB") == 2
    assert set_asides.count("Full-and-Open") == 2


@pytest.mark.parametrize("row_id", [r.doc_id for r in gen.MATRIX])
def test_each_generated_doc_has_required_sections(row_id: str) -> None:
    """Spec §5 — every doc has # Solicitation, Sections A-H, Section I."""
    row = next(r for r in gen.MATRIX if r.doc_id == row_id)
    body = gen.build_document(row, snapshot_date="2026-06-09")

    # # Part / solicitation header
    assert body.startswith(f"# Solicitation {row.doc_id}"), \
        f"missing top-level # header in {row_id}"

    # Every ## Section A through H present
    for letter in "ABCDEFGH":
        assert f"## Section {letter}" in body, \
            f"{row_id} missing Section {letter}"

    # Section I (clause list)
    assert "## Section I" in body, f"{row_id} missing Section I clause list"

    # No real CO names / SAM.gov refs / real solicitation numbers
    # (synthetic-data contract — spec §6).
    forbidden = ["SAM.gov", "Solicitation Number W", "Contracting Officer:"]
    for bad in forbidden:
        assert bad not in body, f"{row_id} contains forbidden substring: {bad}"


def test_docs_within_target_size_band() -> None:
    """Spec §3 row 7 — 10-30 KB per doc."""
    for row in gen.MATRIX:
        body = gen.build_document(row, snapshot_date="2026-06-09")
        n = len(body.encode("utf-8"))
        assert 5_000 <= n <= 35_000, \
            f"{row.doc_id} size={n} bytes outside 5–35 KB tolerance band"


def test_build_all_generates_ten_files(tmp_path: Path) -> None:
    summary = gen.build_all(tmp_path, snapshot_date="2026-06-09", force=True)
    assert summary["written"] == 10
    assert summary["skipped"] == 0
    assert summary["total"] == 10

    md_files = sorted(p.relative_to(tmp_path).as_posix()
                       for p in tmp_path.rglob("*.md")
                       if p.name != "MANIFEST.md")
    assert len(md_files) == 10
    assert sum(1 for p in md_files if p.startswith("gsa-fas/")) == 5
    assert sum(1 for p in md_files if p.startswith("dod-dla/")) == 5


def test_build_all_idempotent_without_force(tmp_path: Path) -> None:
    """Spec §7 step 6 — re-run without ``--force`` skips existing files."""
    gen.build_all(tmp_path, snapshot_date="2026-06-09", force=True)
    summary = gen.build_all(tmp_path, snapshot_date="2026-06-09", force=False)
    assert summary["written"] == 0
    assert summary["skipped"] == 10


def test_build_all_force_overwrites(tmp_path: Path) -> None:
    gen.build_all(tmp_path, snapshot_date="2026-06-09", force=True)
    # Mutate one file
    one = next(tmp_path.rglob("SOL-GSA-001-*.md"))
    one.write_text("# tampered\n", encoding="utf-8")

    summary = gen.build_all(tmp_path, snapshot_date="2026-06-09", force=True)
    assert summary["written"] == 10
    assert "Solicitation SOL-GSA-001" in one.read_text(encoding="utf-8")


def test_manifest_sha256_matches_file_contents(tmp_path: Path) -> None:
    """Spec §5.1 — MANIFEST.sha256 lines match sha256 of each doc."""
    gen.build_all(tmp_path, snapshot_date="2026-06-09", force=True)
    manifest = (tmp_path / "MANIFEST.sha256").read_text(encoding="utf-8")
    line_re = re.compile(r"^([0-9a-f]{64})\s\s(.+)$")
    for line in manifest.splitlines():
        if not line.strip():
            continue
        m = line_re.match(line)
        assert m, f"malformed manifest line: {line!r}"
        digest, rel = m.group(1), m.group(2)
        target = tmp_path / rel
        assert target.exists(), f"manifest references missing file: {rel}"
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        assert actual == digest, f"sha mismatch for {rel}"


def test_committed_corpus_files_exist_and_match_manifest() -> None:
    """The 10 docs committed under docs/reference/synthetic-solicitations/
    align with the spec-§5 layout and the MANIFEST.sha256.
    """
    if not _CORPUS_DIR.exists():
        pytest.skip("corpus dir not present in this checkout")

    gsa = sorted((_CORPUS_DIR / "gsa-fas").glob("SOL-GSA-*.md"))
    dod = sorted((_CORPUS_DIR / "dod-dla").glob("SOL-DOD-*.md"))
    assert len(gsa) == 5, f"expected 5 GSA docs, got {len(gsa)}"
    assert len(dod) == 5, f"expected 5 DoD docs, got {len(dod)}"

    sha_file = _CORPUS_DIR / "MANIFEST.sha256"
    assert sha_file.exists(), "MANIFEST.sha256 missing"
    line_re = re.compile(r"^([0-9a-f]{64})\s\s(.+)$")
    for line in sha_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        m = line_re.match(line)
        assert m, f"malformed manifest line: {line!r}"
        digest, rel = m.group(1), m.group(2)
        target = _CORPUS_DIR / rel
        assert target.exists(), f"committed manifest references missing file: {rel}"
        assert hashlib.sha256(target.read_bytes()).hexdigest() == digest, \
            f"committed corpus sha mismatch for {rel}"


def test_committed_corpus_passes_content_scan() -> None:
    """Every committed synthetic doc passes the ADR-0011 D1.1 scan."""
    if not _CORPUS_DIR.exists():
        pytest.skip("corpus dir not present in this checkout")
    from app.ingest import scanner
    from app.ingest.loaders import markdown as md_loader

    for path in sorted(_CORPUS_DIR.rglob("*.md")):
        if path.name == "MANIFEST.md":
            continue
        body = path.read_text(encoding="utf-8")
        chunks = md_loader.load(body)
        flagged = scanner.scan_chunks(chunks)
        assert not flagged, (
            f"{path.name} tripped the content scanner: "
            f"{[(i, r.flag) for i, r in flagged]}"
        )
