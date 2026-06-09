"""PDF loader — spec §9.3.

Uses ``pypdf``. Text per-page, concatenated with ``\\n\\n`` separators.
Lines matching ``^Section [A-M] —`` are promoted to ``##`` markdown headers
before passing to :func:`app.ingest.loaders.markdown.load` so PDFs reuse
the §9.1 chunking path.

Scope-out (spec §15):
    OCR for scanned PDFs — Phase 1.5
    Image / table extraction — Phase 1.5

If extracted text is shorter than 100 chars total, the loader raises
``PdfTextExtractionFailed`` and the handler maps it to a 422 response with
``error="pdf_text_extraction_failed"`` (matches audit-log outcome variant
in spec §8.1).
"""
from __future__ import annotations

import io
import re
from typing import Any

from app.ingest.loaders import markdown as _md_loader


class PdfTextExtractionFailed(Exception):
    """Raised when pypdf yields too little text to be useful (scanned PDF)."""


_MIN_EXTRACTED_CHARS = 100
_SECTION_HEADER_RE = re.compile(r"^(Section\s+[A-M](?:\s*[—\-:].*)?)$", re.MULTILINE)


def load(raw: bytes) -> list[dict[str, Any]]:
    """Extract text from PDF bytes; return markdown-loader-style records."""
    try:
        import pypdf
    except ImportError as exc:  # pragma: no cover — dep required at runtime
        raise RuntimeError("pypdf not installed; add to requirements.txt") from exc

    try:
        reader = pypdf.PdfReader(io.BytesIO(raw))
    except Exception as exc:
        raise PdfTextExtractionFailed(f"pypdf failed to open: {exc}") from exc

    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")

    full = "\n\n".join(pages).strip()
    if len(full) < _MIN_EXTRACTED_CHARS:
        raise PdfTextExtractionFailed(
            f"PDF yielded only {len(full)} chars of extractable text "
            f"(< {_MIN_EXTRACTED_CHARS}). Likely scanned/image PDF — OCR is "
            f"out of scope for Phase 1 (m2-synthetic-corpus.md §15)."
        )

    # Promote "Section X —" lines to ## markdown headers so the markdown
    # loader produces section-aware chunks (spec §9.3 header heuristic).
    promoted = _SECTION_HEADER_RE.sub(r"## \1", full)

    return _md_loader.load(promoted)
