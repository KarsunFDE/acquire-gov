"""Chunk content scanner — ``chunk_quality_flag`` regex per ADR-0011 D1.1.

Inspects raw chunk text for known prompt-injection patterns *before* embedding.
Matches do NOT silently rewrite content; the ingest handler aborts the whole
document and returns 422 ``chunk_quality_flag_raised`` (spec §8 step 8 —
fail-closed gate; partial ingest is not a behavior).

False positives are tolerated by design — they trigger eyes-on-the-corpus at
build time (ADR-0011 D1, "Consequences").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# Patterns from ADR-0011 D1 (defense layer 1). Conservative — favors recall
# over precision; corpus-build review absorbs false positives.
_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(ignore|disregard)\s+(previous|prior|all)\s+(instructions|context)"),
    re.compile(r"(?i)\bsystem\s*:\s*you\s+are\b"),
    re.compile(r"(?i)you\s+are\s+now\s+(in\s+)?[a-z]+\s+mode"),
    re.compile(r"(?i)(print|reveal|show)\s+(your\s+)?(system\s+)?prompt"),
    # Chat-format role markers escaping retrieved-context wrapper
    re.compile(r"<\s*/?\s*(system|assistant|user)\s*>", re.IGNORECASE),
    re.compile(r"\[\s*(system|assistant)\s*\]", re.IGNORECASE),
    # Wrapper-escape attempts (closing the <retrieved_context> delimiter)
    re.compile(r"</\s*retrieved_context\s*>", re.IGNORECASE),
]


@dataclass(frozen=True)
class ScanResult:
    """Per-chunk scan outcome.

    Attributes
    ----------
    flag:
        Human-readable reason string when a pattern matched; ``None`` for
        clean chunks. This becomes the ``chunk_quality_flag`` field on the
        chunk document (ADR-0006 D2 + ADR-0011 D1.1).
    """

    flag: str | None

    @property
    def flagged(self) -> bool:
        return self.flag is not None


def scan_text(text: str) -> ScanResult:
    """Return a :class:`ScanResult` for a single chunk's text."""
    for pat in _PATTERNS:
        if pat.search(text):
            return ScanResult(flag=f"injection_pattern:{pat.pattern[:40]}")
    return ScanResult(flag=None)


def scan_chunks(chunks: Iterable[dict]) -> list[tuple[int, ScanResult]]:
    """Scan an iterable of chunk dicts; return ``[(index, ScanResult), ...]``.

    Only flagged chunks are included in the return list — clean chunks are
    omitted so the caller can short-circuit on empty.
    """
    flagged: list[tuple[int, ScanResult]] = []
    for idx, chunk in enumerate(chunks):
        result = scan_text(chunk.get("text", ""))
        if result.flagged:
            flagged.append((idx, result))
    return flagged
