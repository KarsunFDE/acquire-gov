"""Hand-built query-side guardrail.

Spec: docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §3 stage 2, §4.1, §10.
ADR:  ADR-0011 D2 (managed Bedrock Guardrails OOS per PRD §7;
      hand-built layered Guardrails-equivalent).

Pattern catalog + thresholds live in ``app.guardrails_patterns`` (pre-staged
to keep adversarial phrasing out of this module). This file owns the
``QueryGuardrails.evaluate`` contract: regex layer first, length-based
LLM-judge escalation second (ADR-0011 D2 Layer 1 + Layer 2). The
Nova-Micro classifier call is stubbed for Phase 1 and will be wired to
``app.bedrock_client`` in Phase 1.5 (ADR-0009 D2).

Audit-log discipline (spec §9 ``query_blocked``): every reject writes via
``app.audit.write_audit_log`` with ``action="query_blocked"``, the
reject reason, the query's SHA-256 hash, and the tenant_id. The raw query
is NOT stored on reject (ADR-0011 D2 — query is potentially adversarial
input).
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from typing import Literal

from app.guardrails_patterns import (
    JAILBREAK_PATTERNS,
    LLM_REVIEW_LENGTH_THRESHOLD,
    MAX_QUERY_CHARS,
)

log = logging.getLogger("ai-orchestrator.guardrails")


RejectReason = Literal["query_too_long", "jailbreak_pattern", "off_topic"]


@dataclass
class GuardrailDecision:
    """Result of a single guardrail evaluation.

    ``action="pass"`` → caller proceeds. ``action="reject"`` → caller
    returns 403 ``query_blocked`` per spec §9.
    """

    action: Literal["pass", "reject"]
    reason: str = ""


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _audit_reject(
    *,
    query: str,
    tenant_id: str,
    reason: RejectReason,
    request_id: str | None = None,
) -> None:
    """Write the spec §9 ``query_blocked`` audit row.

    Lazy-imports ``app.audit`` so the guardrail module loads even if the
    audit module is mid-refactor; tests monkeypatch ``write_audit_log``
    directly. Raw query is NEVER passed — only the hash (ADR-0011 D2).
    """
    try:
        from app import audit as _audit_mod  # noqa: PLC0415
    except ImportError:  # pragma: no cover — audit always shipped with C7
        log.warning("audit module unavailable; query_blocked NOT persisted")
        return
    writer = getattr(_audit_mod, "write_audit_log", None)
    if writer is None:  # pragma: no cover
        return
    rid = request_id or str(uuid.uuid4())
    try:
        writer(
            action="query_blocked",
            tenant_id=tenant_id,
            request_id=rid,
            outcome="query_blocked",
            reason=reason,
            query_hash=_sha256(query),
        )
    except Exception as exc:  # pragma: no cover — audit fallback already swallows
        log.warning("query_blocked audit insert failed: %s", exc)


class QueryGuardrails:
    """Hand-built query-side filter.

    Layer 1 (regex): cheap, deterministic — catches the known-bad pattern
    catalog in ``app.guardrails_patterns``.
    Layer 2 (LLM judge): escalation for borderline queries longer than
    ``LLM_REVIEW_LENGTH_THRESHOLD``. Phase 1 stubs the classifier to
    always return ``"on_topic"``; Phase 1.5 wires Nova Micro via
    ``app.bedrock_client`` (ADR-0011 D2).

    Managed Bedrock Guardrails OOS per PRD §7. This class is the
    Guardrails-equivalent; see ADR-0011 D2 for the rationale.
    """

    def evaluate(
        self,
        query: str,
        tenant_id: str,
        *,
        request_id: str | None = None,
    ) -> GuardrailDecision:
        """Apply layered filters to ``query``.

        Order (first reject wins):
          1. Length cap → ``query_too_long``
          2. Regex catalog → ``jailbreak_pattern``
          3. LLM-judge (only for borderline-length) → ``off_topic``
          4. Otherwise → ``pass``

        Rejects write an audit row via ``_audit_reject`` (raw query NOT
        stored — only SHA-256 hash, per ADR-0011 D2).
        """
        if len(query) > MAX_QUERY_CHARS:
            decision = GuardrailDecision(action="reject", reason="query_too_long")
            _audit_reject(
                query=query,
                tenant_id=tenant_id,
                reason="query_too_long",
                request_id=request_id,
            )
            return decision

        for pat in JAILBREAK_PATTERNS:
            if pat.search(query):
                decision = GuardrailDecision(
                    action="reject", reason="jailbreak_pattern"
                )
                _audit_reject(
                    query=query,
                    tenant_id=tenant_id,
                    reason="jailbreak_pattern",
                    request_id=request_id,
                )
                return decision

        if self._needs_llm_review(query):
            verdict = self._nova_micro_classifier(query)
            if verdict == "off_topic":
                decision = GuardrailDecision(action="reject", reason="off_topic")
                _audit_reject(
                    query=query,
                    tenant_id=tenant_id,
                    reason="off_topic",
                    request_id=request_id,
                )
                return decision

        return GuardrailDecision(action="pass")

    def _needs_llm_review(self, query: str) -> bool:
        """Length-based escalation heuristic (ADR-0011 D2 Layer 2)."""
        return len(query) > LLM_REVIEW_LENGTH_THRESHOLD

    def _nova_micro_classifier(self, query: str) -> str:
        """Stub for Phase 1 — Phase 1.5 wires ``amazon.nova-micro-v1:0``
        via ``app.bedrock_client`` per ADR-0011 D2.

        Returns ``"on_topic"`` always so Phase 1 borderline queries pass
        through; tests override this method directly to exercise the
        ``off_topic`` reject path.
        """
        return "on_topic"
