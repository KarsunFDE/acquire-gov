"""C7 — append-only audit_log writer (schema v1).

Spec: docs/specs/m2-retrieval-pipeline.md §8 (schema v1 full layout).
ADR: ADR-0008 D3 (auditLogWriter role, sync write-through, append-only).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app import audit


# --- Validation guards -----------------------------------------------------

def test_write_requires_tenant_id() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        audit.write_audit_log("retrieval_only", tenant_id="", request_id="r1")


def test_write_requires_request_id() -> None:
    with pytest.raises(ValueError, match="request_id"):
        audit.write_audit_log("retrieval_only", tenant_id="t1", request_id="")


# --- File-fallback path (Mongo unavailable) --------------------------------

def test_write_falls_back_to_file_when_mongo_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fallback = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_FILE_FALLBACK", fallback)
    monkeypatch.setattr(audit, "_get_collection", lambda: None)
    audit.reset_for_tests()

    rid = audit.write_audit_log(
        "retrieval_only",
        tenant_id="tenant_A",
        request_id="req-42",
        query="evaluation factors",
        outcome="retrieved",
    )
    assert rid.startswith("file:")
    assert fallback.exists()
    lines = fallback.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    # Schema v1 invariants.
    assert record["schema_version"] == 1
    assert record["tenant_id"] == "tenant_A"
    assert record["request_id"] == "req-42"
    assert record["action"] == "retrieval_only"
    assert record["outcome"] == "retrieved"
    # Query is hashed; raw query also retained inside request{} only.
    assert "query_hash" in record["request"]
    assert record["request"]["query"] == "evaluation factors"
    assert "ts" in record


# --- Mongo path ------------------------------------------------------------

def test_write_inserts_via_pymongo_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_coll = MagicMock()
    fake_coll.insert_one.return_value.inserted_id = "abc123"
    monkeypatch.setattr(audit, "_get_collection", lambda: fake_coll)

    rid = audit.write_audit_log(
        "retrieval_and_generate",
        tenant_id="tenant_A",
        request_id="req-7",
        outcome="draft_returned",
    )
    assert rid == "abc123"
    fake_coll.insert_one.assert_called_once()
    record = fake_coll.insert_one.call_args.args[0]
    assert record["schema_version"] == 1
    assert record["action"] == "retrieval_and_generate"
    assert record["outcome"] == "draft_returned"


# --- Schema v1 record shape ------------------------------------------------

def test_record_serializes_generation_with_hashed_prompt_completion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Spec §8: prompt + completion stored as sha256 hashes, NEVER raw."""
    fallback = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_FILE_FALLBACK", fallback)
    monkeypatch.setattr(audit, "_get_collection", lambda: None)

    audit.write_audit_log(
        "retrieval_and_generate",
        tenant_id="tenant_A",
        request_id="req-9",
        outcome="draft_returned",
        generation={
            "model": "anthropic.claude-sonnet-4-5",
            "prompt": "RAW PROMPT — must not be persisted",
            "completion": "RAW COMPLETION — must not be persisted",
            "input_tokens": 100,
            "output_tokens": 200,
            "citations": [{"chunk_id": "c1", "far_part": "IV"}],
        },
    )
    record = json.loads(fallback.read_text(encoding="utf-8").strip())
    gen = record["generation"]
    assert "prompt" not in gen
    assert "completion" not in gen
    assert len(gen["prompt_hash"]) == 64  # sha256 hex
    assert len(gen["completion_hash"]) == 64
    # Citations kept RAW (spec §8 explicit).
    assert gen["citations"] == [{"chunk_id": "c1", "far_part": "IV"}]


def test_record_includes_retrieval_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fallback = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_FILE_FALLBACK", fallback)
    monkeypatch.setattr(audit, "_get_collection", lambda: None)

    audit.write_audit_log(
        "retrieval_only",
        tenant_id="tenant_A",
        request_id="req-10",
        outcome="retrieved",
        retrieval={
            "retriever_class": "MongoDBAtlasHybridSearchRetriever",
            "vector_weight": 0.5,
            "fulltext_weight": 2.0,
            "gate_decision": "pass",
        },
    )
    record = json.loads(fallback.read_text(encoding="utf-8").strip())
    assert record["retrieval"]["gate_decision"] == "pass"


# --- Mongo write failure surfaces (spec §9 — caller maps to 503) -----------

def test_mongo_write_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_coll = MagicMock()
    fake_coll.insert_one.side_effect = audit.PyMongoError("write failed")
    monkeypatch.setattr(audit, "_get_collection", lambda: fake_coll)

    with pytest.raises(audit.PyMongoError):
        audit.write_audit_log(
            "retrieval_only",
            tenant_id="t1",
            request_id="r1",
            outcome="retrieved",
        )
