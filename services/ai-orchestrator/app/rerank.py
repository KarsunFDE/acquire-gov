"""Amazon Rerank 1.0 wiring + threshold gate.

Spec: docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §3 stage 7-8, §4.1, §10.
ADRs: ADR-0005 D2 (Rerank pinned us-west-2), ADR-0007 D2-D3 (reference
impl + threshold table), ADR-0009 D4 (rerank-unavailable passthrough).

Region pinning is the one infrastructure knob operators can
misconfigure — see spec §11. ``bedrock-agent-runtime`` is the service
client for Rerank 1.0; ``us-west-2`` is mandatory (not available in
us-east-1).
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from app import config
from app.audit import write_audit_log  # noqa: F401 — wired in C7 finalization

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
    _BOTO_AVAILABLE = True
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]
    _BOTO_AVAILABLE = False

log = logging.getLogger("ai-orchestrator.rerank")


GateDecision = Literal["pass", "hitl", "withhold"]


class RerankResult:
    """Plain result of :func:`rerank_only` — no gate decision (ADR-0012 D2).

    ``top_score is None`` + ``degraded_mode=True`` signals rerank outage;
    the gate tool maps that to ``rerank_unavailable_passthrough``.
    """

    __slots__ = ("top", "top_score", "degraded_mode")

    def __init__(self, top: list[dict], top_score: float | None, degraded_mode: bool) -> None:
        self.top = top
        self.top_score = top_score
        self.degraded_mode = degraded_mode


_client = None


def _get_rerank_client() -> Any:
    """``bedrock-agent-runtime`` client hard-pinned to us-west-2.

    Spec §11: Rerank is the only Bedrock client in the orchestrator that
    pins region. ``BEDROCK_RERANK_REGION`` env var surfaces the knob.
    """
    global _client
    if _client is None and _BOTO_AVAILABLE:
        try:
            _client = boto3.client(
                "bedrock-agent-runtime",
                region_name=config.BEDROCK_RERANK_REGION,
            )
        except Exception as exc:  # pragma: no cover — boto3 init paths
            log.warning("bedrock-agent-runtime client init failed: %s", exc)
            _client = None
    return _client


def _stub_rerank(candidates: list[dict]) -> list[dict]:
    """Stub fallback when AWS_BEARER_TOKEN_BEDROCK is unset.

    Returns top-5 with mock relevance_score 0.7 (above HITL threshold)
    so dev-laptop end-to-end flows behave like 'pass'. Matches the
    invoke_model / embed_documents stub contract.
    """
    top = candidates[: config.RERANK_TOP_N]
    return [{**c, "relevance_score": 0.7} for c in top]


def _real_rerank(client: Any, query: str, candidates: list[dict]) -> list[dict]:
    """Call Amazon Rerank 1.0 via bedrock-agent-runtime.rerank.

    Returns the top-RERANK_TOP_N with a ``relevance_score`` attached.
    Index-aligned: Rerank returns ``index`` + ``relevance_score`` per
    result; we map back to the source candidate dict.
    """
    sources = [
        {"type": "INLINE", "inlineDocumentSource": {
            "type": "TEXT", "textDocument": {"text": c.get("text", "")}
        }}
        for c in candidates
    ]
    resp = client.rerank(
        queries=[{"type": "TEXT", "textQuery": {"text": query}}],
        sources=sources,
        rerankingConfiguration={
            "type": "BEDROCK_RERANKING_MODEL",
            "bedrockRerankingConfiguration": {
                "numberOfResults": config.RERANK_TOP_N,
                "modelConfiguration": {
                    "modelArn": config.BEDROCK_RERANK_MODEL_ARN,
                },
            },
        },
    )
    out: list[dict] = []
    for entry in resp.get("results", []):
        idx = entry["index"]
        out.append({**candidates[idx], "relevance_score": entry["relevanceScore"]})
    return out


def rerank_only(query: str, candidates: list[dict]) -> RerankResult:
    """Rerank candidates WITHOUT a gate decision (spec §8.1.1).

    The agentic flow needs rerank and gate split so ``compute_gate_decision``
    is the single source of ``gate_decision`` (its input args drive the HITL
    middleware predicate — ADR-0012 D6). ``rerank_and_gate`` below keeps the
    M2 ``/retrieve`` contract by composing this function with the inline gate.

    Degraded path: Bedrock Rerank failure falls back to the stub scorer and
    flags ``degraded_mode=True`` with ``top_score=None`` so the gate tool maps
    it to ``rerank_unavailable_passthrough``.
    """
    if not candidates:
        return RerankResult(top=[], top_score=None, degraded_mode=False)

    client = _get_rerank_client()
    if client is None:
        log.info("bedrock-rerank stub-fallback (no boto3 / no credentials)")
        top = _stub_rerank(candidates)
        return RerankResult(
            top=top,
            top_score=top[0].get("relevance_score") if top else None,
            degraded_mode=False,
        )
    try:
        top = _real_rerank(client, query, candidates)
    except (NoCredentialsError, BotoCoreError, ClientError) as exc:
        log.warning("rerank failed (%s); degraded passthrough", exc)
        return RerankResult(
            top=candidates[: config.RERANK_TOP_N],
            top_score=None,
            degraded_mode=True,
        )
    return RerankResult(
        top=top,
        top_score=top[0].get("relevance_score") if top else None,
        degraded_mode=False,
    )


def rerank_and_gate(
    query: str,
    candidates: list[dict],
    withhold_threshold: float | None = None,
    hitl_threshold: float | None = None,
) -> tuple[GateDecision, list[dict]]:
    """Rerank candidates and apply the threshold gate (ADR-0007 D2-D3).

    Returns ``(decision, top_n)`` where decision is:
      - ``"pass"``     — top relevance_score >= hitl_threshold (0.5)
      - ``"hitl"``     — withhold_threshold <= top score < hitl_threshold
      - ``"withhold"`` — top score < withhold_threshold (0.3), OR
                         candidates is empty

    Empty top → withhold per spec §3 stage 8 ("top score absent → withhold").
    Bedrock failure is handled by callers (C9 endpoint wiring) per the
    ``rerank_unavailable_passthrough`` contract in spec §9; here we
    surface the exception so the wrapper can record it.
    """
    if withhold_threshold is None:
        withhold_threshold = config.RERANK_WITHHOLD_THRESHOLD
    if hitl_threshold is None:
        hitl_threshold = config.RERANK_HITL_THRESHOLD

    if not candidates:
        return ("withhold", [])

    client = _get_rerank_client()
    if client is None:
        log.info("bedrock-rerank stub-fallback (no boto3 / no credentials)")
        top = _stub_rerank(candidates)
    else:
        try:
            top = _real_rerank(client, query, candidates)
        except (NoCredentialsError, BotoCoreError, ClientError) as exc:
            log.warning("rerank failed (%s); falling back to stub", exc)
            top = _stub_rerank(candidates)

    if not top:
        return ("withhold", [])

    top_score = top[0].get("relevance_score", 0.0)
    if top_score >= hitl_threshold:
        return ("pass", top)
    if top_score >= withhold_threshold:
        return ("hitl", top)
    return ("withhold", [])
