"""MongoDBSaver singleton + thread_id helpers (Phase 0, P0.3 — ADR-0012 D4).

Design reference: docs/specs/m1-agentic-drafting/design-reference.md §10.

The checkpointer is process-wide; ``build_mongodb_saver()`` returns a singleton
so the PyMongo connection pool stays warm across requests. TTL is explicitly
``None`` — paused HITL runs must survive multi-day CO delays (ADR-0012 D4).
"""
from __future__ import annotations

from functools import lru_cache

from app import config


@lru_cache(maxsize=1)
def build_mongodb_saver():
    """Process-wide singleton ``MongoDBSaver``.

    PyMongo client is thread-safe; the saver uses a connection pool.
    Lazy-imports langgraph + pymongo so unit tests that never touch the
    checkpointer don't need the optional dependency importable.
    """
    from langgraph.checkpoint.mongodb import MongoDBSaver  # noqa: PLC0415
    from pymongo import MongoClient  # noqa: PLC0415

    client = MongoClient(config.MONGO_URI)
    return MongoDBSaver(
        client=client,
        db_name=config.MONGO_DB,
        checkpoint_collection_name=config.AGENT_CHECKPOINT_COLLECTION,
        writes_collection_name=config.AGENT_CHECKPOINT_WRITES_COLLECTION,
        ttl=config.AGENT_CHECKPOINT_TTL,  # None — multi-day pause requirement
    )


def thread_id_for(*, solicitation_id: str, section_id: str, request_id: str) -> str:
    """Single source-of-truth thread_id format (ADR-0012 D4)."""
    return f"{solicitation_id}:{section_id}:{request_id}"


def parse_thread_id(thread_id: str) -> tuple[str, str, str]:
    """Inverse of :func:`thread_id_for`. Raises ``ValueError`` on malformed input."""
    parts = thread_id.split(":", 2)
    if len(parts) != 3 or not all(parts):
        raise ValueError(f"malformed thread_id: {thread_id!r}")
    sol, sec, req = parts
    return sol, sec, req
