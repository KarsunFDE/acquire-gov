"""
bedrock_client.py — thin wrapper around boto3's BedrockRuntime client.

Per D-060: real Bedrock InvokeModel authorized from W2 onward as an
explicit exception to D-050 (AWS deferral). AWS *managed services*
(Knowledge Bases for Bedrock, Agents-for-Bedrock, OpenSearch Managed)
remain deferred to W5 — this file is InvokeModel only.

⚠ DELIBERATE: brownfield-debt items preserved across this Bedrock wiring:
  - Item 4 — caller endpoints still return raw dicts; no Pydantic
    response_model on /draft-solicitation, /draft-amendment, /answer-qa,
    or /eval/ssdd-draft.
  - Item 5 — legacy_chain.py still in place; 3 endpoints below thread
    through draft_with_legacy_chain (Drafting Wizard via /draft-solicitation,
    Amendment Editor via /draft-amendment, notification-copy via
    Notifier.cparWindowOpened upstream — invoked by Spring side).
  - Item 6 — no correlation-id forwarded into the Bedrock InvokeModel call.
  - Item 7 — pinecone-client still in requirements.txt; no `import pinecone`
    in this module.

Stub fallback: if boto3 cannot resolve credentials (typical pre-W5 dev
laptop), invoke_model returns a stub response shaped like the real one so
the rest of the stack still flows. Real Bedrock InvokeModel runs whenever
AWS_PROFILE / AWS_ACCESS_KEY_ID / EC2 IMDS resolves.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
from typing import Any

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
    _BOTO_AVAILABLE = True
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]
    _BOTO_AVAILABLE = False

log = logging.getLogger("ai-orchestrator.bedrock")

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-7-sonnet-20250219-v1:0",
)
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# C3 — Titan v2 @ 512 (ADR-0005 D2 / m2-retrieval-pipeline.md §10).
# Read from app.config when available so env overrides flow through one
# place; fall back to spec defaults if config has not loaded (parallel-
# track import safety).
try:
    from app import config as _cfg  # type: ignore[import-not-found]
    _EMBED_MODEL_ID = _cfg.BEDROCK_EMBED_MODEL
    _EMBED_DIMS = _cfg.BEDROCK_EMBED_DIMS
except ImportError:  # pragma: no cover
    _EMBED_MODEL_ID = os.environ.get("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0")
    _EMBED_DIMS = int(os.environ.get("BEDROCK_EMBED_DIMS", "512"))


_client = None


def _get_client():
    global _client
    if _client is None and _BOTO_AVAILABLE:
        try:
            _client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        except Exception as exc:
            log.warning("bedrock-runtime client init failed: %s", exc)
            _client = None
    return _client


def invoke_model(prompt: str, *, system: str | None = None,
                  max_tokens: int = 1024,
                  temperature: float = 0.2) -> dict[str, Any]:
    """
    InvokeModel against Anthropic Claude via Bedrock.

    Returns a dict with keys:
      - body: the model's text response (or stub)
      - model: Bedrock model id
      - region: AWS region
      - stub: True if returned the stub fallback

    ⚠ Item 4 — return shape NOT Pydantic-validated.
    ⚠ Item 6 — no correlation-id forwarded.
    """
    client = _get_client()
    if client is None:
        log.info("bedrock stub-fallback (no boto3 / no credentials)")
        return _stub(prompt)

    messages = [{"role": "user", "content": prompt}]
    body: dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        body["system"] = system

    try:
        resp = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body).encode("utf-8"),
        )
        payload = json.loads(resp["body"].read())
        # Anthropic-on-Bedrock returns {"content": [{"type":"text","text":"..."}], ...}
        text = ""
        for block in payload.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        return {
            "body": text or json.dumps(payload),
            "model": BEDROCK_MODEL_ID,
            "region": AWS_REGION,
            "stub": False,
        }
    except (NoCredentialsError, BotoCoreError, ClientError) as exc:
        log.warning("bedrock InvokeModel failed (%s); returning stub", exc)
        return _stub(prompt)


def _stub(prompt: str) -> dict[str, Any]:
    return {
        "body": f"[stub] would-Bedrock-respond to: {prompt[:80]}",
        "model": BEDROCK_MODEL_ID,
        "region": AWS_REGION,
        "stub": True,
    }


# ---------- C3 — embeddings (Titan v2 @ 512) -----------------------------

def _stub_embed(text: str, dims: int) -> list[float]:
    """Deterministic stub vector — hash-seeded for repeatable test runs.

    Stub path triggers when AWS_BEARER_TOKEN_BEDROCK is unset and boto3
    cannot resolve any other credential source. Same fallback contract as
    invoke_model above.
    """
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(dims)]


def _real_embed_one(client: Any, text: str) -> list[float]:
    """One Titan v2 invocation; returns the 512-float embedding."""
    body = json.dumps({
        "inputText": text,
        "dimensions": _EMBED_DIMS,
        "normalize": True,
    }).encode("utf-8")
    resp = client.invoke_model(
        modelId=_EMBED_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    payload = json.loads(resp["body"].read())
    vec = payload.get("embedding") or []
    if len(vec) != _EMBED_DIMS:
        log.warning(
            "titan-embed returned %d dims; expected %d", len(vec), _EMBED_DIMS
        )
    return list(vec)


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Batch-embed ``texts`` with Titan v2 @ 512 dims.

    Returns one ``list[float]`` per input. Empty input → empty output.

    Failure / stub behavior:
      - No boto3 → all-stub.
      - boto3 present but credentials missing → per-call retry that
        raises NoCredentialsError; we catch and return stubs (matches
        invoke_model fallback contract, ADR-0005 D2 stub).
      - Per-item Bedrock 5xx → stub for that item; log warning. Full
        tenacity-retry envelope is C9 territory (m2-retrieval-pipeline.md
        §3 stage 5).

    Spec: docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §10 BEDROCK_EMBED_DIMS=512;
    ADR-0005 D2 quality-cost lever.
    """
    if not texts:
        return []

    client = _get_client()
    if client is None:
        log.info("bedrock-embed stub-fallback (no boto3 / no credentials)")
        return [_stub_embed(t, _EMBED_DIMS) for t in texts]

    out: list[list[float]] = []
    for t in texts:
        try:
            out.append(_real_embed_one(client, t))
        except (NoCredentialsError, BotoCoreError, ClientError) as exc:
            log.warning("titan-embed failed (%s); stub for this item", exc)
            out.append(_stub_embed(t, _EMBED_DIMS))
    return out


def embed_query(text: str) -> list[float]:
    """Single-text embed — convenience for the /retrieve query path."""
    return embed_documents([text])[0]
