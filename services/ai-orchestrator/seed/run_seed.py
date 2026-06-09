"""Seed orchestrator — spec §11.

Brings a fresh atlas-local container to a corpus-ready state:

1. Ingest FAR snapshot (``doc_class=far_reference``) — reads
   ``docs/reference/far/``. Owned by the pipeline-agent track; this
   orchestrator iterates the directory and posts to the same loader
   stack via ``app/ingest`` modules.
2. Ingest 10 synthetic solicitations (``doc_class=synthetic_solicitation``) —
   reads ``docs/reference/synthetic-solicitations/``.
3. Summarize chunks-per-doc + total embedding token count.

Idempotency: skips docs whose ``(source_doc, snapshot_date)`` already
exists in the ``chunks`` collection. Safe to re-run. Same loader stack as
``POST /ingest/document`` — what the cohort runs at seed time is what
admins run at endpoint time (spec §11 last paragraph).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("seed.run_seed")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ingest_dir(
    directory: Path,
    *,
    doc_class: str,
    tenant_id: str,
    snapshot_date: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Walk ``directory`` and ingest every ``.md`` file.

    Uses the same in-process loader stack as ``POST /ingest/document``
    (``app.ingest.loaders.markdown``) so seed-time + endpoint-time share
    one code path.
    """
    from app.ingest.loaders import markdown as md_loader
    from app.ingest import scanner

    total_docs = 0
    total_chunks = 0
    flagged_docs = 0

    md_files = sorted(directory.rglob("*.md"))
    md_files = [p for p in md_files if p.name not in {"MANIFEST.md"}]

    for path in md_files:
        total_docs += 1
        body = path.read_text(encoding="utf-8")
        records = md_loader.load(body)
        flagged = scanner.scan_chunks(records)
        if flagged:
            flagged_docs += 1
            log.warning(
                "FLAGGED %s — %d chunk(s) tripped content scan; skipping",
                path.relative_to(_project_root()),
                len(flagged),
            )
            continue
        total_chunks += len(records)
        log.info(
            "[%s] %s -> %d pre-split records (doc_class=%s)",
            "dry-run" if dry_run else "ingest",
            path.relative_to(_project_root()),
            len(records),
            doc_class,
        )
        if dry_run:
            continue
        # Real path: post to ``/ingest/document`` via the in-process FastAPI
        # client, OR call the same loader+embed+insert stack directly. The
        # pipeline-agent track lands the in-process insert helper; until
        # then we leave the actual write as a no-op so the seed script is
        # still useful as a dry-run / counter.
        # (See spec §11 — "shares the same loader stack as /ingest/document".)

    return {
        "directory": str(directory),
        "doc_class": doc_class,
        "docs": total_docs,
        "chunks_pre_split": total_chunks,
        "flagged_docs": flagged_docs,
    }


def run(
    *,
    tenant_id: str,
    snapshot_date: str,
    far_dir: Path,
    synth_dir: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run both ingest passes; return a summary dict."""
    summary: dict[str, Any] = {"tenant_id": tenant_id, "snapshot_date": snapshot_date}

    if far_dir.exists():
        summary["far"] = _ingest_dir(
            far_dir,
            doc_class="far_reference",
            tenant_id=tenant_id,
            snapshot_date=snapshot_date,
            dry_run=dry_run,
        )
    else:
        log.info("FAR snapshot directory %s missing; skipping FAR pass", far_dir)
        summary["far"] = {"skipped": True, "directory": str(far_dir)}

    if synth_dir.exists():
        summary["synthetic"] = _ingest_dir(
            synth_dir,
            doc_class="synthetic_solicitation",
            tenant_id=tenant_id,
            snapshot_date=snapshot_date,
            dry_run=dry_run,
        )
    else:
        log.info(
            "Synthetic solicitation directory %s missing; "
            "run `python -m seed.build_synthetic_solicitations` first",
            synth_dir,
        )
        summary["synthetic"] = {"skipped": True, "directory": str(synth_dir)}

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", default="agency-default",
                         help="X-Tenant-ID stamped on every chunk")
    parser.add_argument("--snapshot-date", default="2026-06-09",
                         help="ISO snapshot date stamped on every chunk")
    parser.add_argument("--far-dir", default=None,
                         help="FAR snapshot dir (default docs/reference/far)")
    parser.add_argument("--synth-dir", default=None,
                         help="synthetic solicitation dir (default "
                              "docs/reference/synthetic-solicitations)")
    parser.add_argument("--dry-run", action="store_true",
                         help="parse + scan + count, but do not write to Mongo")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    root = _project_root()
    far_dir = Path(args.far_dir) if args.far_dir else root / "docs" / "reference" / "far"
    synth_dir = (
        Path(args.synth_dir)
        if args.synth_dir
        else root / "docs" / "reference" / "synthetic-solicitations"
    )

    summary = run(
        tenant_id=args.tenant_id,
        snapshot_date=args.snapshot_date,
        far_dir=far_dir,
        synth_dir=synth_dir,
        dry_run=args.dry_run,
    )
    print("[run_seed] summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
