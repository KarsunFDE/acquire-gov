"""P0.2 — every M1 config knob reachable with documented default.

Spec: docs/specs/m1-agentic-drafting/phases/0-foundation.md §6 P0.2.
Defaults assume a clean env (CI does not set the M1 knobs).
"""
from __future__ import annotations

import pathlib

import pytest

from app import config

EXPECTED_DEFAULTS = {
    "BEDROCK_EXTRACT_MODEL": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "BEDROCK_EXTRACT_MAX_RETRIES": 1,
    "BEDROCK_CRITIC_MODEL": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "SET_ASIDE_STRICT_EXTRA": False,
    "GATE_PASS_THRESHOLD": 0.55,
    "GATE_WITHHOLD_THRESHOLD": 0.40,
    "AGENT_CHECKPOINT_COLLECTION": "agent_checkpoints",
    "AGENT_CHECKPOINT_WRITES_COLLECTION": "agent_checkpoint_writes",
    "AGENT_CHECKPOINT_TTL": None,
    "AGENT_ORPHAN_SWEEP_INTERVAL_SECONDS": 3600,
    "AGENT_ORPHAN_AGE_DAYS": 30,
    "MAX_BATCH_FAN_OUT": 2,
    "LANGSMITH_TRACING": False,
    "LANGSMITH_PROJECT": "acquire-gov-m1-draft",
}


@pytest.mark.parametrize("knob", sorted(EXPECTED_DEFAULTS))
def test_knob_reachable_with_default(knob: str, monkeypatch):
    monkeypatch.delenv(knob, raising=False)
    assert hasattr(config, knob), f"config missing {knob}"
    import os
    if knob in os.environ:  # pragma: no cover — env leaked into CI
        pytest.skip(f"{knob} set in environment; default not assertable")
    assert getattr(config, knob) == EXPECTED_DEFAULTS[knob]


def test_langsmith_api_key_attr_exists():
    assert hasattr(config, "LANGSMITH_API_KEY")


def test_checkpoint_ttl_not_env_readable():
    """ADR-0012 D4 — TTL is a Python None literal, not an env knob."""
    src = pathlib.Path(config.__file__).read_text(encoding="utf-8")
    assert "AGENT_CHECKPOINT_TTL = None" in src


def test_env_example_documents_every_new_var():
    """.env.example lists every env-readable M1 knob (P0.2 gate)."""
    env_example = (
        pathlib.Path(config.__file__).resolve().parents[3] / ".env.example"
    )
    text = env_example.read_text(encoding="utf-8")
    env_readable = [k for k in EXPECTED_DEFAULTS if k != "AGENT_CHECKPOINT_TTL"]
    env_readable.append("LANGSMITH_API_KEY")
    for knob in env_readable:
        assert f"{knob}=" in text, f".env.example missing {knob}"
