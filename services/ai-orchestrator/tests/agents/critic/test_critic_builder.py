"""P4.2 — critic agent builder integration (scripted fake model).

Drives the REAL create_agent loop: the scripted model calls all 3 tools
(programmatic ones execute for real; the LLM one is stubbed), then emits the
final ConsistencyReport.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("langchain.agents", reason="langchain v1 required")

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from app.agents.critic import builder as critic_builder_mod
from app.agents.critic.builder import CRITIC_TOOLS, build_consistency_critic_agent
from app.agents.critic.tools import lm_consistency as lm_mod
from app.agents.schemas import LMAlignmentReport


class _ScriptedChatModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):  # noqa: ANN001
        return self


_FINAL_REPORT_ARGS = {
    "solicitation_id": "sol-1",
    "run_id": "sol-1:critic:req-1",
    "lm_alignment": {
        "mismatches": [], "overall_severity": "info",
        "model": "amazon.nova-lite-v1:0", "input_tokens": 0, "output_tokens": 0,
    },
    "set_aside_consistency": {
        "mismatches": [{
            "set_aside": "SDVOSB", "expected_reps": ["52.219-27"],
            "actual_reps": [], "missing": ["52.219-27"], "extra": [],
            "severity": "warn",
        }],
        "overall_severity": "warn",
    },
    "clin_coverage": {"gaps": [], "overall_severity": "info"},
    "overall_severity": "warn",
    "blocks_submit": False,
    "model_used": "amazon.nova-lite-v1:0",
    "timestamp": "2026-06-11T12:00:00Z",
}


def test_tool_surface():
    assert {t.name for t in CRITIC_TOOLS} == {
        "verify_l_m_consistency",
        "check_set_aside_consistency",
        "check_clin_coverage",
    }


def test_critic_agent_runs_three_tools_then_reports(monkeypatch):
    # LLM tool stubbed; programmatic tools run for real.
    parsed = LMAlignmentReport(
        mismatches=[], overall_severity="info",
        model="tool-filled", input_tokens=0, output_tokens=0,
    )
    raw = SimpleNamespace(usage_metadata={})
    chat = SimpleNamespace(
        with_structured_output=lambda *_a, **_kw: SimpleNamespace(
            invoke=lambda prompt: {"parsed": parsed, "raw": raw, "parsing_error": None}
        )
    )
    monkeypatch.setattr(lm_mod, "_critic_chat", lambda: chat)

    script = iter([
        AIMessage(content="", tool_calls=[
            {"name": "verify_l_m_consistency",
             "args": {"section_l": "L text", "section_m": "M text"}, "id": "t1"},
            {"name": "check_set_aside_consistency",
             "args": {"set_aside": "SDVOSB", "section_k_text": "no reps"}, "id": "t2"},
            {"name": "check_clin_coverage",
             "args": {"section_b": "0001 services", "section_c": "0001",
                      "section_f": "0001", "section_l": "0001"}, "id": "t3"},
        ]),
        AIMessage(content="", tool_calls=[
            {"name": "ConsistencyReport", "args": _FINAL_REPORT_ARGS, "id": "t4"},
        ]),
    ])
    monkeypatch.setattr(
        critic_builder_mod, "_critic_harness_chat",
        lambda: _ScriptedChatModel(messages=script),
    )

    agent = build_consistency_critic_agent()
    assert agent.name == "consistency_critic"
    result = agent.invoke({"messages": [{"role": "user", "content": "check sol-1"}]})

    # All 3 critic tools produced ToolMessages (the 4th is the structured-
    # output tool the harness injects for response_format).
    tool_msgs = [m for m in result["messages"]
                 if m.type == "tool" and m.name != "ConsistencyReport"]
    assert len(tool_msgs) == 3
    assert {m.name for m in tool_msgs} == {
        "verify_l_m_consistency", "check_set_aside_consistency", "check_clin_coverage",
    }

    report = result["structured_response"]
    assert report.overall_severity == "warn"
    assert report.blocks_submit is False
    assert report.set_aside_consistency.mismatches[0].missing == ["52.219-27"]
