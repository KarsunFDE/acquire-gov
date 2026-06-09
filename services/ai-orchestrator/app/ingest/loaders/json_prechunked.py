"""JSON-prechunked loader — spec §9.4.

Body shape::

    {
      "chunks": [
        {"text": str, "metadata": {"far_part"?, "far_section"?,
                                    "far_subsection"?, "far_clause"?,
                                    "title"?}},
        ...
      ]
    }

Second-stage ``RecursiveCharacterTextSplitter`` is **skipped** for this
format (handler branches in ``app/api/ingest.py``) — caller asserts the
chunks. Embedding + content scan still run.

Caller-provided embeddings are NOT accepted, eliminating dim/model
mismatch risk (spec §9.4).
"""
from __future__ import annotations

import json
from typing import Any


class JsonPrechunkedMalformed(Exception):
    """Raised when the JSON body does not match the expected schema."""


def load(raw: bytes) -> list[dict[str, Any]]:
    """Parse ``raw`` as JSON and return chunk records."""
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JsonPrechunkedMalformed(f"invalid JSON: {exc}") from exc

    if not isinstance(payload, dict) or "chunks" not in payload:
        raise JsonPrechunkedMalformed("expected object with 'chunks' key")
    chunks = payload["chunks"]
    if not isinstance(chunks, list) or not chunks:
        raise JsonPrechunkedMalformed("'chunks' must be a non-empty list")

    out: list[dict[str, Any]] = []
    for i, c in enumerate(chunks):
        if not isinstance(c, dict) or "text" not in c or not isinstance(c["text"], str):
            raise JsonPrechunkedMalformed(
                f"chunk[{i}] missing required string 'text' field"
            )
        if not c["text"].strip():
            raise JsonPrechunkedMalformed(f"chunk[{i}] has empty text")
        # Reject caller-supplied embedding to eliminate dim/model drift
        if "embedding" in c:
            raise JsonPrechunkedMalformed(
                f"chunk[{i}]: caller-supplied embeddings are rejected (spec §9.4)"
            )
        rec: dict[str, Any] = {"text": c["text"]}
        meta = c.get("metadata") or {}
        if not isinstance(meta, dict):
            raise JsonPrechunkedMalformed(f"chunk[{i}].metadata must be an object")
        for k in ("far_part", "far_section", "far_subsection", "far_clause", "title"):
            v = meta.get(k)
            if v:
                rec[k] = v
        out.append(rec)
    return out
