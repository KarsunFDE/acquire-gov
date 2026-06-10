"""C3 — Bedrock embeddings tests (Titan v2 @ 512).

Spec: docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §10 (BEDROCK_EMBED_DIMS=512);
ADR-0005 D2 (Titan v2 model + dimensions).

Covers:
  - Stub fallback returns 512-float deterministic vectors when no
    boto3 client is available (or AWS_BEARER_TOKEN_BEDROCK unset).
  - Real path invokes ``invoke_model`` with the right modelId, dims,
    and contentType; returns the embedding payload's 512-float array.
  - Per-item Bedrock failure degrades to a stub for that item.
  - ``embed_query`` is a 1-text convenience.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app import bedrock_client


# --- stub-fallback path ----------------------------------------------------

def test_embed_documents_stub_when_no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bedrock_client, "_get_client", lambda: None)
    vecs = bedrock_client.embed_documents(["alpha", "beta"])
    assert len(vecs) == 2
    assert all(len(v) == bedrock_client._EMBED_DIMS for v in vecs)
    # All floats in [-1, 1]
    assert all(-1.0 <= x <= 1.0 for v in vecs for x in v)


def test_embed_documents_stub_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bedrock_client, "_get_client", lambda: None)
    a = bedrock_client.embed_documents(["same input"])
    b = bedrock_client.embed_documents(["same input"])
    assert a == b  # hash-seeded RNG → exact match


def test_embed_documents_empty_input_returns_empty() -> None:
    assert bedrock_client.embed_documents([]) == []


# --- real-bedrock path -----------------------------------------------------

def _fake_response(vec: list[float]) -> dict:
    body = MagicMock()
    body.read.return_value = json.dumps({"embedding": vec}).encode("utf-8")
    return {"body": body}


def test_embed_documents_invokes_titan_with_correct_modelid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.invoke_model.return_value = _fake_response([0.1] * bedrock_client._EMBED_DIMS)
    monkeypatch.setattr(bedrock_client, "_get_client", lambda: client)

    vecs = bedrock_client.embed_documents(["chunk one"])
    assert len(vecs) == 1
    assert len(vecs[0]) == bedrock_client._EMBED_DIMS

    # Inspect the invoke_model call args
    call = client.invoke_model.call_args
    assert call.kwargs["modelId"] == bedrock_client._EMBED_MODEL_ID
    assert call.kwargs["contentType"] == "application/json"
    sent_body = json.loads(call.kwargs["body"].decode("utf-8"))
    assert sent_body["inputText"] == "chunk one"
    assert sent_body["dimensions"] == bedrock_client._EMBED_DIMS


def test_embed_documents_batches_each_item_through_invoke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.invoke_model.return_value = _fake_response([0.0] * bedrock_client._EMBED_DIMS)
    monkeypatch.setattr(bedrock_client, "_get_client", lambda: client)

    bedrock_client.embed_documents(["a", "b", "c"])
    assert client.invoke_model.call_count == 3


def test_embed_documents_per_item_failure_falls_back_to_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from botocore.exceptions import ClientError

    err = ClientError({"Error": {"Code": "ThrottlingException", "Message": "x"}}, "InvokeModel")
    client = MagicMock()
    client.invoke_model.side_effect = [
        err,
        _fake_response([0.5] * bedrock_client._EMBED_DIMS),
    ]
    monkeypatch.setattr(bedrock_client, "_get_client", lambda: client)

    vecs = bedrock_client.embed_documents(["fail-me", "succeed"])
    assert len(vecs) == 2
    assert len(vecs[0]) == bedrock_client._EMBED_DIMS  # stub
    assert len(vecs[1]) == bedrock_client._EMBED_DIMS  # real (all 0.5)
    assert vecs[1] == [0.5] * bedrock_client._EMBED_DIMS


def test_embed_query_returns_single_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bedrock_client, "_get_client", lambda: None)
    vec = bedrock_client.embed_query("a query")
    assert isinstance(vec, list)
    assert len(vec) == bedrock_client._EMBED_DIMS


def test_embed_dims_matches_config_spec() -> None:
    """Spec §10: BEDROCK_EMBED_DIMS=512 (ADR-0005 D2 quality-cost lever)."""
    assert bedrock_client._EMBED_DIMS == 512
