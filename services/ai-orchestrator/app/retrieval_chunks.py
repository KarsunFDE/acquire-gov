"""Retrieval-side chunker — thin wrapper over the ingest two-stage splitter.

Spec: docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §5 module layout.

The ingest path (``app/api/ingest.py`` → ``app/ingest/loaders/markdown.py``
+ second-stage ``RecursiveCharacterTextSplitter``) handles uploads coming
through the admin endpoint. Retrieval-side code (the FAR seed runner and
any on-the-fly re-chunk during eval / drift-detection) needs the same
two-stage pipeline without the HTTP envelope.

Rather than duplicate the splitter logic, this module re-exports the
ingest loader and a small helper that bundles the two stages exactly as
the ingest router does (ADR-0006 D1 chunk_size=1200, overlap=150). The
ingest path is the authoritative implementation; if its loader changes,
this wrapper inherits the change for free.

Public surface:

- :func:`split_markdown` — markdown bytes/str → list of chunk dicts
  carrying ``far_part`` / ``far_section`` / ``far_subsection`` /
  ``far_clause`` / ``title`` / ``text`` / ``chunk_index`` / ``char_start``
  / ``char_end``.
"""
from __future__ import annotations

from typing import Any

from app.ingest.loaders import markdown as _md


def split_markdown(content: str, *, chunk_size: int | None = None,
                   chunk_overlap: int | None = None) -> list[dict[str, Any]]:
    """Two-stage split for markdown content.

    Stage 1: ``MarkdownHeaderTextSplitter`` (header-aware; preserves
    ``far_part`` / ``far_section`` / ``far_subsection`` metadata).

    Stage 2: ``RecursiveCharacterTextSplitter`` (size-bounded; carries
    metadata into each sub-chunk).

    Defaults pulled from :mod:`app.config` (ADR-0010 D3); explicit kwargs
    override for test scenarios.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    if chunk_size is None or chunk_overlap is None:
        try:
            from app import config as _cfg
        except ImportError:
            _cfg = None  # type: ignore[assignment]
        chunk_size = chunk_size or (getattr(_cfg, "CHUNK_SIZE", 1200) if _cfg else 1200)
        chunk_overlap = chunk_overlap or (getattr(_cfg, "CHUNK_OVERLAP", 150) if _cfg else 150)

    stage1 = _md.load(content)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    out: list[dict[str, Any]] = []
    chunk_index = 0
    for rec in stage1:
        text = rec.get("text", "")
        if not text.strip():
            continue
        inherited = {k: v for k, v in rec.items() if k != "text"}
        sub_texts = splitter.split_text(text) or [text]
        char_cursor = 0
        for sub in sub_texts:
            start = text.find(sub, char_cursor)
            if start < 0:
                start = char_cursor
            end = start + len(sub)
            char_cursor = end
            out.append({
                **inherited,
                "text": sub,
                "chunk_index": chunk_index,
                "char_start": start,
                "char_end": end,
            })
            chunk_index += 1
    return out
