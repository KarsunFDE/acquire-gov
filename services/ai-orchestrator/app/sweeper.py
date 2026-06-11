"""Orphan-thread sweeper (ADR-0012 D8.2; design ref §6.3).

Marks checkpoints abandoned that are older than ``AGENT_ORPHAN_AGE_DAYS`` and
never reached a terminal state. Does NOT delete — hard-delete is a deferred
Phase 1.5 chore. Sweeper failures are logged and retried next interval; they
never bubble into the request path.

Also exposes :func:`mark_abandoned` — the ``/abandon`` endpoint's direct
"CO walked away" marker (same sentinel field the sweeper sets).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app import config

log = logging.getLogger("ai-orchestrator.sweeper")


def _checkpoint_collection() -> Any:
    """Lazy collection handle — tests monkeypatch this."""
    from pymongo import MongoClient  # noqa: PLC0415

    client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=1000)
    return client[config.MONGO_DB][config.AGENT_CHECKPOINT_COLLECTION]


def _now() -> datetime:
    """Wall clock — tests monkeypatch this to force the orphan window."""
    return datetime.now(timezone.utc)


def mark_abandoned(run_id: str) -> int:
    """Set ``abandoned=True`` on every checkpoint row of a thread.

    Returns the number of matched documents (0 → caller maps to 404).
    Does not delete; the sweeper window still applies for reclaim accounting.
    """
    coll = _checkpoint_collection()
    result = coll.update_many(
        {"thread_id": run_id}, {"$set": {"abandoned": True}}
    )
    return int(result.matched_count)


def _doc_age_cutoff_filter(cutoff: datetime) -> dict:
    """Match checkpoint docs older than the cutoff.

    langgraph-checkpoint-mongodb docs carry an ObjectId ``_id`` whose
    generation time is the insert wall-clock — portable across saver
    versions without depending on the serialized checkpoint payload.
    """
    from bson import ObjectId  # noqa: PLC0415

    return {"_id": {"$lt": ObjectId.from_datetime(cutoff)}}


def sweep_once() -> int:
    """One sweep pass. Returns the number of threads marked.

    Criteria (design ref §6.3): older than AGENT_ORPHAN_AGE_DAYS AND not
    already abandoned AND no terminal structured_response in checkpoint
    state. The terminal check is conservative: a thread is skipped if ANY
    of its rows carries the terminal marker metadata.
    """
    from app import audit as audit_mod  # noqa: PLC0415

    coll = _checkpoint_collection()
    cutoff = _now() - timedelta(days=config.AGENT_ORPHAN_AGE_DAYS)

    stale = coll.find(
        {**_doc_age_cutoff_filter(cutoff), "abandoned": {"$ne": True}}
    )
    threads: set[str] = {d["thread_id"] for d in stale if d.get("thread_id")}

    marked = 0
    for thread_id in sorted(threads):
        coll.update_many({"thread_id": thread_id}, {"$set": {"abandoned": True}})
        marked += 1
        try:
            audit_mod.write_audit_log(
                action="agent_orphan_swept",
                tenant_id="system",
                request_id=f"sweeper:{thread_id}",
                outcome="abandoned",
                run_id=thread_id,
            )
        except Exception as exc:  # pragma: no cover — audit must not stop sweep
            log.error("sweeper audit write failed for %s: %s", thread_id, exc)
    if marked:
        log.info("sweeper marked %d orphan thread(s)", marked)
    return marked


async def sweep_orphan_threads() -> None:
    """Background loop started from app lifespan. Never raises."""
    while True:
        try:
            await asyncio.to_thread(sweep_once)
        except Exception as exc:  # noqa: BLE001 — retried next interval
            log.warning("sweep pass failed (retrying next interval): %s", exc)
        await asyncio.sleep(config.AGENT_ORPHAN_SWEEP_INTERVAL_SECONDS)
