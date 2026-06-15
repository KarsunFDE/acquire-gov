"""P0.3 — checkpointer singleton + thread_id helpers.

Unit tests run anywhere. The integration test (write + read a checkpoint
against atlas-local) auto-skips when Mongo is unreachable so the suite stays
green on machines without the compose stack up.

Spec: docs/specs/m1-agentic-drafting/phases/0-foundation.md §6 P0.3.
"""
from __future__ import annotations

import pytest

from app import config
from app.agents.checkpointer import (
    build_mongodb_saver,
    parse_thread_id,
    thread_id_for,
)


# --- thread_id helpers (pure) -----------------------------------------------


def test_thread_id_round_trip():
    tid = thread_id_for(
        solicitation_id="sol-001", section_id="C", request_id="req-001"
    )
    assert tid == "sol-001:C:req-001"
    assert parse_thread_id(tid) == ("sol-001", "C", "req-001")


def test_thread_id_request_id_may_contain_colons():
    """request_id is the tail segment — split('::', 2) keeps embedded colons."""
    tid = thread_id_for(
        solicitation_id="sol-001", section_id="C", request_id="uuid:with:colons"
    )
    assert parse_thread_id(tid) == ("sol-001", "C", "uuid:with:colons")


@pytest.mark.parametrize("bad", ["", "noseparator", "only:one", "a:b:", ":b:c"])
def test_parse_thread_id_raises_on_malformed(bad: str):
    with pytest.raises(ValueError):
        parse_thread_id(bad)


# --- singleton ----------------------------------------------------------------


def _mongo_up() -> bool:
    try:
        from pymongo import MongoClient

        MongoClient(
            config.MONGO_URI, serverSelectionTimeoutMS=500
        ).admin.command("ping")
        return True
    except Exception:
        return False


def test_build_mongodb_saver_is_lru_cached():
    assert build_mongodb_saver.cache_info().maxsize == 1


@pytest.mark.skipif(not _mongo_up(), reason="atlas-local Mongo not reachable")
def test_checkpoint_write_and_read_back():
    """Integration: write a checkpoint, read it back, verify collections exist."""
    from langchain_core.runnables import RunnableConfig

    saver = build_mongodb_saver()
    assert saver is build_mongodb_saver()  # singleton

    cfg: RunnableConfig = {
        "configurable": {
            "thread_id": "sol-test:C:p03-integration",
            "checkpoint_ns": "",
        }
    }
    checkpoint = {
        "v": 1,
        "id": "p03-checkpoint-0001",
        "ts": "2026-06-11T00:00:00+00:00",
        "channel_values": {"marker": "p03"},
        "channel_versions": {},
        "versions_seen": {},
        "pending_sends": [],
    }
    saver.put(cfg, checkpoint, metadata={"source": "test", "step": 0}, new_versions={})

    fetched = saver.get_tuple(cfg)
    assert fetched is not None
    assert fetched.checkpoint["channel_values"]["marker"] == "p03"

    from pymongo import MongoClient

    db = MongoClient(config.MONGO_URI)[config.MONGO_DB]
    names = db.list_collection_names()
    assert config.AGENT_CHECKPOINT_COLLECTION in names
