"""Citation hard-fail verification.

Spec: docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §3 stage 11, §9.
ADR: ADR-0011 D3 (citation hard-fail).

Every chunk_id cited in a generated completion MUST appear in the
retrieved top-N. Unknown IDs trigger 422 ``citation_verification_failed``
and the audit record preserves the unknown IDs (spec §9).
"""
from __future__ import annotations

from typing import Iterable


class CitationVerificationFailed(Exception):
    """Raised when a generation cites a chunk_id outside the retrieved set."""

    def __init__(self, unknown_ids: list[str]) -> None:
        super().__init__(f"unknown chunk_ids in completion: {unknown_ids}")
        self.unknown_ids = unknown_ids


def _id_set(items: Iterable[dict], key: str) -> set[str]:
    out: set[str] = set()
    for item in items:
        if key not in item:
            continue
        out.add(str(item[key]))
    return out


def verify_citations(
    generation_result: dict,
    retrieved_chunks: list[dict],
) -> bool:
    """Hard-fail if any cited chunk_id is not in the retrieved set.

    ``generation_result`` must contain a ``"citations"`` list whose
    entries carry ``"chunk_id"``. ``retrieved_chunks`` is the top-N
    output of rerank; each entry carries ``"_id"`` (Mongo) or
    ``"chunk_id"`` (post-retrieval normalized form). Both are accepted
    so callers don't have to normalize before this gate.

    Returns ``True`` on success. Raises ``CitationVerificationFailed``
    when one or more cited IDs are unknown — caller maps to HTTP 422
    and writes the unknown_ids to the audit record (spec §9).
    """
    citations = generation_result.get("citations") or []
    cited_ids = _id_set(citations, "chunk_id")

    # Retrieved chunks may have either _id (raw Mongo) or chunk_id
    # (already-mapped). Union both.
    retrieved_ids = _id_set(retrieved_chunks, "_id") | _id_set(
        retrieved_chunks, "chunk_id"
    )

    unknown = cited_ids - retrieved_ids
    if unknown:
        # Sort for determinism in tests + audit-record stability.
        raise CitationVerificationFailed(unknown_ids=sorted(unknown))
    return True
