"""P2.5 — multi-day pause survives a process restart (ADR-0012 D4).

Interrupt a run with the REAL agent graph + MongoDB checkpointer, then
simulate an uvicorn restart by clearing the ``build_mongodb_saver`` lru_cache
(new saver instance, new Mongo client — same collections), rebuild the agent,
and resume. Auto-skips when atlas-local Mongo is unreachable; the in-memory
equivalent (same-process resume) is covered in
tests/agents/test_hitl_interrupt_resume.py.
"""
from __future__ import annotations

import uuid

import pytest

from app import config


def _mongo_up() -> bool:
    try:
        from pymongo import MongoClient

        MongoClient(
            config.MONGO_URI, serverSelectionTimeoutMS=500
        ).admin.command("ping")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _mongo_up(), reason="atlas-local Mongo not reachable")


def test_interrupt_survives_saver_restart(monkeypatch):
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage
    from langgraph.types import Command

    from app.agents import builder as builder_mod
    from app.agents.checkpointer import build_mongodb_saver

    class _ScriptedChatModel(GenericFakeChatModel):
        def bind_tools(self, tools, **kwargs):  # noqa: ANN001
            return self

    final_args = {
        "outcome": "draft_returned",
        "section_text": "L.1 ...",
        "section_id": "L",
        "citations": [],
        "gate_decision": "hitl",
        "requires_human_review": True,
        "rerank_top_score": 0.45,
        "request_id": "req-pr",
        "run_id": "restart-test",
    }
    script = iter([
        AIMessage(content="", tool_calls=[{
            "name": "compute_gate_decision",
            "args": {"rerank_top_score": 0.45},
            "id": "tc1",
        }]),
        AIMessage(content="", tool_calls=[{
            "name": "FinalDraftSection", "args": final_args, "id": "tc2",
        }]),
    ])
    monkeypatch.setattr(
        builder_mod, "_harness_chat", lambda: _ScriptedChatModel(messages=script)
    )

    run_id = f"sol-pr:{uuid.uuid4().hex[:8]}:L:req"
    cfg = {"configurable": {"thread_id": run_id, "tenant_id": "tenant_A"},
           "metadata": {"tenant_id": "tenant_A"}}

    build_mongodb_saver.cache_clear()
    agent = builder_mod.build_section_drafter_agent()
    first = agent.invoke(
        {"messages": [{"role": "user", "content": "draft L"}]}, config=cfg
    )
    assert first.get("__interrupt__"), "expected interrupt before restart"

    # ── simulated restart: drop the saver singleton; rebuild everything ──
    build_mongodb_saver.cache_clear()
    agent2 = builder_mod.build_section_drafter_agent()

    snapshot = agent2.get_state(cfg)
    assert snapshot.next, "checkpoint must still be paused after restart"

    resumed = agent2.invoke(
        Command(resume={"decisions": [{"type": "approve"}]}), config=cfg
    )
    assert resumed["structured_response"].outcome == "draft_returned"
