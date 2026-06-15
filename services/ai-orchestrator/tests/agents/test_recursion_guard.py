"""DEMO-REDESIGN-spec §1 — token-runaway regression guard.

The 2026-06-12 incident: an agent re-emitted the same tool calls every turn and
ran to 2.8M tokens because langchain 1.3.8 binds ``recursion_limit: 9_999`` on
the compiled graph (langgraph #7313). The critic was capped afterward; the
Sonnet drafters were not. These tests prove two things:

1. A looping agent invoked at ``DRAFTER_RECURSION_LIMIT`` dies fast with a
   bounded call count (it raises ``GraphRecursionError`` instead of running
   away). This is the behavioral guard.
2. The production draft invoke config actually SETS that bound — so nobody can
   silently drop it back to the 9_999 default. This is the wiring guard.
"""
from __future__ import annotations

import pytest

pytest.importorskip("langchain.agents", reason="langchain v1 required")

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from app import config


class _AlwaysToolCallModel(BaseChatModel):
    """Fake model that emits the SAME tool call on every turn — the exact loop
    shape of the incident. Never returns a final answer, so only the recursion
    cap can stop it."""

    @property
    def _llm_type(self) -> str:
        return "always-tool-call"

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001 — create_agent calls this
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001
        msg = AIMessage(
            content="",
            tool_calls=[{"name": "loop_tool", "args": {"payload": "x"}, "id": "loop"}],
        )
        return ChatResult(generations=[ChatGeneration(message=msg)])


def test_recursion_limit_kills_tool_loop():
    """A never-terminating agent must raise GraphRecursionError at the bound,
    with the tool invoked a bounded (small) number of times — not thousands."""
    calls: list[int] = []

    @tool
    def loop_tool(payload: str) -> str:
        """Test tool that always re-triggers the model."""
        calls.append(1)
        return "call me again"

    agent = create_agent(
        model=_AlwaysToolCallModel(),
        tools=[loop_tool],
        checkpointer=InMemorySaver(),
    )

    with pytest.raises(GraphRecursionError):
        agent.invoke(
            {"messages": [{"role": "user", "content": "go"}]},
            config={
                "configurable": {"thread_id": "loop-test"},
                "recursion_limit": config.DRAFTER_RECURSION_LIMIT,
            },
        )

    # The whole point: the loop stopped near the cap, nowhere near a runaway.
    # Each super-step is one model turn + one tool turn, so tool calls < limit.
    assert calls, "tool never executed — fake wiring broken"
    assert len(calls) <= config.DRAFTER_RECURSION_LIMIT, (
        f"loop ran {len(calls)} times — recursion cap not enforced"
    )


def test_draft_invoke_config_sets_recursion_limit():
    """Wiring guard: the section-drafter invoke config must carry the bound so
    it can never silently regress to langgraph's 9_999 default."""
    from app.api import draft as draft_mod

    cfg = draft_mod._invoke_config(
        run_id="r", tenant_id="t", co_user_id=None, request_id="req",
        solicitation_id="sol", section_id="C", callbacks=[],
    )
    assert cfg["recursion_limit"] == config.DRAFTER_RECURSION_LIMIT


def test_drafter_recursion_limit_is_bounded():
    """Sanity floor/ceiling — the default must be loop-stopping (small), never
    near the dangerous langgraph default."""
    assert 3 <= config.DRAFTER_RECURSION_LIMIT <= 50
