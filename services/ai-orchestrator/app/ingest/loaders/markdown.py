"""Markdown loader — spec §9.1.

Header map (ADR-0006 D1):
    ``#``   → ``far_part``
    ``##``  → ``far_section``
    ``###`` → ``far_subsection``

``far_clause`` is extracted from header text or first line via regex
``\\d{2}\\.\\d{3}(-\\d+)?`` when present.
"""
from __future__ import annotations

import re
from typing import Any

from langchain_text_splitters import MarkdownHeaderTextSplitter

_CLAUSE_RE = re.compile(r"\b(\d{2}\.\d{3}(?:-\d+)?)\b")

# Map per ADR-0006 D1.
_HEADERS = [
    ("#", "far_part"),
    ("##", "far_section"),
    ("###", "far_subsection"),
]


def load(content: str) -> list[dict[str, Any]]:
    """Parse markdown ``content`` into ordered pre-split chunk dicts.

    Each output dict carries ``text`` plus any of ``far_part``,
    ``far_section``, ``far_subsection``, ``far_clause``, ``title`` that the
    splitter populated. The handler's second-stage
    ``RecursiveCharacterTextSplitter`` further breaks sections that exceed
    ``CHUNK_SIZE`` (1200 chars per ADR-0006 D1).
    """
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS,
        strip_headers=False,
    )
    docs = splitter.split_text(content)

    out: list[dict[str, Any]] = []
    for doc in docs:
        # langchain Document → dict; metadata keys mirror our header map
        text = doc.page_content
        meta = dict(doc.metadata or {})
        rec: dict[str, Any] = {"text": text}
        for k in ("far_part", "far_section", "far_subsection"):
            if meta.get(k):
                rec[k] = meta[k]
        # Pull far_clause from the most-specific header text we have
        clause_source = (
            meta.get("far_subsection") or meta.get("far_section") or meta.get("far_part") or text[:200]
        )
        m = _CLAUSE_RE.search(clause_source)
        if m:
            rec["far_clause"] = m.group(1)
        # Title heuristic: first non-empty line after stripping the leading "#"
        # markers. Cheap and sufficient for citation display.
        for line in text.splitlines():
            stripped = line.lstrip("# ").strip()
            if stripped:
                rec.setdefault("title", stripped[:160])
                break
        out.append(rec)
    return out
