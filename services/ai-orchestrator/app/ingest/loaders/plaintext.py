"""Plain-text loader — spec §9.2.

No structural headers to detect; single-stage
``RecursiveCharacterTextSplitter`` is the only split. Caller-provided
``far_part``/``far_section`` from the ``metadata`` form field, if present,
applies to every chunk in the document.

Plaintext is the escape hatch for unstructured uploads — retrieval quality
is lower than markdown for the same content (spec §9.2 note).
"""
from __future__ import annotations

from typing import Any


def load(content: str) -> list[dict[str, Any]]:
    """Return a single pre-split record carrying the raw text.

    The handler's second-stage splitter applies on top — we don't run it
    here so the markdown and plaintext paths share one downstream splitter.
    """
    text = content.strip()
    if not text:
        return []
    return [{"text": text}]
