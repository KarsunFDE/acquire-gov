"""P1.4 — build_section_drafter_agent integration test (all stubs).

Constructs the real v1.0 ``create_agent`` graph with a fake chat model and an
in-memory checkpointer; asserts the wiring (tools, name, structured output
contract) without any Bedrock/Mongo dependency.
"""
from __future__ import annotations

import pytest

pytest.importorskip("langchain.agents", reason="langchain v1 required")

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from app.agents import builder as builder_mod
from app.agents.builder import SECTION_DRAFTER_TOOLS, build_section_drafter_agent

EXPECTED_TOOL_NAMES = {
    "retrieve_far_clauses",
    "retrieve_related_solicitations",
    "extract_section_requirements",
    "compute_gate_decision",
    "draft_section_text",
    "validate_citations",
}


@pytest.fixture()
def stubbed(monkeypatch):
    from langgraph.checkpoint.memory import InMemorySaver

    fake = GenericFakeChatModel(messages=iter([]))
    monkeypatch.setattr(builder_mod, "_harness_chat", lambda: fake)
    monkeypatch.setattr(builder_mod, "build_mongodb_saver", lambda: InMemorySaver())
    return fake


def test_tool_surface_matches_adr_0012(stubbed):
    assert {t.name for t in SECTION_DRAFTER_TOOLS} == EXPECTED_TOOL_NAMES


def test_agent_constructs_and_compiles(stubbed):
    agent = build_section_drafter_agent()
    assert agent is not None
    assert agent.name == "section_drafter"
    # Compiled graph carries the tools node + model node.
    node_names = set(agent.get_graph().nodes)
    assert any("tools" in n for n in node_names), node_names


def test_every_tool_has_docstring_and_schema(stubbed):
    """v1.0 requires type hints (they define the tool's input schema) and
    docstrings (model-facing usage steering)."""
    for t in SECTION_DRAFTER_TOOLS:
        assert t.description, f"{t.name} missing docstring"
        assert t.args_schema is not None, f"{t.name} missing schema"
        # tenant safety: no tool exposes tenant_id to the model
        assert "tenant_id" not in t.args_schema.model_json_schema().get("properties", {})
