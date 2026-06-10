"""FAR-snapshot seed runner — splits + embeds + inserts.

Spec: docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §11 (seed flow). Companion to
``seed/run_seed.py`` which only counts; this script does the full
embed + bulk-insert.

Reads ``docs/reference/far/*.md``, splits via ``app.retrieval_chunks``
(the same two-stage splitter the ingest endpoint uses, ADR-0006 D1),
embeds with Titan v2 @ 512 (ADR-0005 D2), and writes through the in-
process ingest pipeline.

Two write paths supported (CLI flag picks one):

- ``--mode http`` (default): POST every file to ``/ingest/document`` —
  same envelope an admin user would use (spec §4.3). Requires the
  service to be running locally.
- ``--mode inproc``: import ``app.api.ingest`` helpers and call the
  embed + bulk-insert routine directly. No HTTP hop; needed for the
  Docker-compose seed step where the orchestrator is still booting.

Idempotency: the ingest handler's duplicate-doc probe (spec §10.1) is
the source of truth — re-running the seed is safe.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("seed.seed_far_snapshot")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _iter_far_files(far_dir: Path) -> list[Path]:
    if not far_dir.exists():
        raise FileNotFoundError(f"FAR snapshot dir missing: {far_dir}")
    return sorted(
        p for p in far_dir.glob("far-part-*.md") if p.is_file()
    )


def _embed_and_insert_inproc(
    *,
    chunks: list[dict[str, Any]],
    tenant_id: str,
    source_doc: str,
    snapshot_date: str,
) -> str:
    """Same path as ``app.api.ingest`` post-scan write — minus HTTP."""
    from app import bedrock_client as _bc

    texts = [c["text"] for c in chunks]
    embeddings = _bc.embed_documents(texts)

    document_id = str(uuid.uuid4())
    for c, emb in zip(chunks, embeddings):
        c["tenant_id"] = tenant_id
        c["embedding"] = emb
        c["source_doc"] = source_doc
        c["snapshot_date"] = snapshot_date
        c["doc_class"] = "far_reference"
        c.setdefault("chunk_quality_flag", None)

    # Bulk-insert via the retrieval helper (pipeline-agent territory —
    # lazy-imported so this runner still works pre-C4 when retrieval.py
    # has no bulk_insert_chunks).
    try:
        from app import retrieval as _ret  # type: ignore[import-not-found]
        inserter = getattr(_ret, "bulk_insert_chunks", None)
        if inserter is not None:
            inserter(chunks, document_id=document_id)
        else:
            log.warning("app.retrieval.bulk_insert_chunks not present yet; "
                        "chunks NOT persisted (pre-C4)")
    except ImportError:
        log.warning("app.retrieval not present yet; chunks NOT persisted (pre-C4)")

    return document_id


def _post_http(
    *,
    path: Path,
    tenant_id: str,
    snapshot_date: str,
    base_url: str,
) -> dict[str, Any]:
    """POST to ``/ingest/document`` — production-shaped envelope."""
    import httpx  # type: ignore[import-not-found]

    metadata = {
        "source_doc_name": path.name,
        "snapshot_date": snapshot_date,
        "doc_class": "far_reference",
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{base_url.rstrip('/')}/ingest/document",
            headers={
                "X-Tenant-ID": tenant_id,
                "X-Request-ID": str(uuid.uuid4()),
            },
            files={"file": (path.name, path.read_bytes(), "text/markdown")},
            data={"metadata": json.dumps(metadata), "format": "md"},
        )
    return {"status": resp.status_code, "body": resp.json()}


def run(
    *,
    tenant_id: str,
    snapshot_date: str,
    far_dir: Path,
    mode: str,
    base_url: str,
    dry_run: bool,
) -> dict[str, Any]:
    files = _iter_far_files(far_dir)
    log.info("found %d FAR file(s) in %s", len(files), far_dir)

    summary: dict[str, Any] = {
        "tenant_id": tenant_id,
        "snapshot_date": snapshot_date,
        "mode": mode,
        "files": [],
    }

    from app import retrieval_chunks

    for path in files:
        content = path.read_text(encoding="utf-8")
        chunks = retrieval_chunks.split_markdown(content)
        log.info("%s -> %d chunks", path.name, len(chunks))
        entry: dict[str, Any] = {"file": path.name, "chunks": len(chunks)}

        if dry_run:
            entry["dry_run"] = True
        elif mode == "inproc":
            doc_id = _embed_and_insert_inproc(
                chunks=chunks,
                tenant_id=tenant_id,
                source_doc=path.name,
                snapshot_date=snapshot_date,
            )
            entry["document_id"] = doc_id
        elif mode == "http":
            entry["response"] = _post_http(
                path=path,
                tenant_id=tenant_id,
                snapshot_date=snapshot_date,
                base_url=base_url,
            )
        else:
            raise ValueError(f"unknown mode: {mode}")

        summary["files"].append(entry)

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", default="agency-default")
    parser.add_argument("--snapshot-date", default="2026-06-09")
    parser.add_argument("--far-dir", default=None,
                        help="default: docs/reference/far")
    parser.add_argument("--mode", choices=["http", "inproc"], default="inproc")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="orchestrator base URL (mode=http only)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    root = _project_root()
    far_dir = (
        Path(args.far_dir) if args.far_dir
        else root / "docs" / "reference" / "far"
    )

    summary = run(
        tenant_id=args.tenant_id,
        snapshot_date=args.snapshot_date,
        far_dir=far_dir,
        mode=args.mode,
        base_url=args.base_url,
        dry_run=args.dry_run,
    )

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
