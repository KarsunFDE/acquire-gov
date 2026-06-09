"""Audit-log writer skeleton (finalized in C7).

Spec: docs/specs/m2-retrieval-pipeline.md §8 (schema v1).
ADR: ADR-0008 D3 (append-only audit log, auditLogWriter role binding).

C6 ships the skeleton signature so ``rerank.py`` and downstream
endpoints can import it without circular dependencies. C7 swaps the
stdout log for a real pymongo insert + schema-v1 record builder + file
fallback.
"""
from __future__ import annotations

import logging

log = logging.getLogger("ai-orchestrator.audit")


def write_audit_log(
    action: str,
    tenant_id: str,
    request_id: str,
    **kwargs: object,
) -> str:
    """Insert one ``audit_log`` row per ADR-0008 D3 schema v1.

    Skeleton (C6): log to stdout in dev. Real Mongo insert + schema-v1
    record builder + file fallback land in C7.

    Returns the inserted ``_id`` (skeleton: a placeholder string).
    """
    log.info(
        "audit-log skeleton write: action=%s tenant_id=%s request_id=%s extra=%s",
        action, tenant_id, request_id, kwargs,
    )
    return f"skeleton:{request_id}"
