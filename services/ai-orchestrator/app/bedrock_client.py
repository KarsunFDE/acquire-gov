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

import json
import logging
import os
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
