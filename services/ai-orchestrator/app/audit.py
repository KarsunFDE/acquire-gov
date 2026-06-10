"""Append-only audit-log writer — schema v1.

Spec: docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §8 (full schema v1).
ADR: ADR-0008 D3 (auditLogWriter role, sync write-through, additive
evolution only).

Role binding: orchestrator service user binds to ``auditLogWriter``
(privileges: ``insert``, ``find`` only — explicitly NO ``update``, NO
``remove``). Schema version is ``1`` from day one; future evolution is
additive only (append-only DB role enforces this at the resource
level).

Write-through: ``write_audit_log`` is **synchronous**. Callers must not
return an API response until this returns.

Fallback: if pymongo cannot connect (typical dev laptop without
atlas-local running), we write the record to a local file as a
last-resort durability path. Spec §3 stage 12 says Mongo-write-failure
must surface a 503 in the real path; the file fallback is dev-only and
emits a logged warning.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import config

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
    _PYMONGO_AVAILABLE = True
except ImportError:  # pragma: no cover
    MongoClient = None  # type: ignore[assignment, misc]
    PyMongoError = Exception  # type: ignore[assignment, misc]
    _PYMONGO_AVAILABLE = False

log = logging.getLogger("ai-orchestrator.audit")

# Dev fallback: file path is overridable for tests.
AUDIT_FILE_FALLBACK = Path(
    os.environ.get("AUDIT_FILE_FALLBACK", "/tmp/audit_log_fallback.jsonl")
)


_mongo_client: Any = None
_collection: Any = None


def _get_collection() -> Any:
    """Lazy MongoClient → audit_log collection.

    Returns ``None`` when pymongo is unavailable, connection fails, or
    the server is unreachable; callers fall back to file. The probe
    issues one ``ismaster`` (admin.command("ping")) so a typical dev
    laptop without atlas-local running stays on the file fallback
    instead of blocking the request path.
    """
    global _mongo_client, _collection
    if _collection is not None:
        return _collection
    if not _PYMONGO_AVAILABLE:
        return None
    try:
        _mongo_client = MongoClient(
            config.MONGO_URI, serverSelectionTimeoutMS=500
        )
        # Force a server-selection probe so unreachable hosts fail
        # here, not in insert_one (which would propagate as 503).
        _mongo_client.admin.command("ping")
        _collection = _mongo_client[config.MONGO_DB][config.AUDIT_LOG_COLLECTION]
    except Exception as exc:
        log.warning("mongo client init/probe failed: %s", exc)
        _collection = None
    return _collection


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _build_record(
    action: str,
    tenant_id: str,
    request_id: str,
    *,
    actor: dict | None = None,
    query: str | None = None,
    retrieval: dict | None = None,
    generation: dict | None = None,
    hitl: dict | None = None,
    outcome: str,
    **extras: Any,
) -> dict:
    """Build a schema-v1 record per spec §8.

    Hashes ``query`` and ``generation.prompt``/``completion`` if raw
    strings are supplied (ADR-0008 D3 — never store raw prompt or
    completion; raw query allowed only as hash).
    Citations array is kept RAW per spec §8.
    """
    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc),
        "tenant_id": tenant_id,
        "request_id": request_id,
        "actor": actor or {"user_id": None, "role": None, "session_id": None},
        "action": action,
        "outcome": outcome,
        "schema_version": 1,
    }
    if query is not None:
        record["request"] = {"query": query, "query_hash": _sha256(query)}
    if retrieval is not None:
        record["retrieval"] = retrieval
    if generation is not None:
        # Hash prompt + completion if caller supplied raw text.
        gen = dict(generation)
        for raw_key, hash_key in (("prompt", "prompt_hash"), ("completion", "completion_hash")):
            if raw_key in gen:
                gen[hash_key] = _sha256(gen.pop(raw_key))
        record["generation"] = gen
    if hitl is not None:
        record["hitl"] = hitl
    # Schema v1 evolution is additive-only (ADR-0008 D3); accept extra
    # top-level fields callers may pass (e.g., gate_decision before C9
    # wraps it into the retrieval{} block).
    for k, v in extras.items():
        record.setdefault(k, v)
    return record


def _write_file_fallback(record: dict) -> str:
    """Append record as one JSON line to the fallback file (dev only)."""
    try:
        AUDIT_FILE_FALLBACK.parent.mkdir(parents=True, exist_ok=True)
        # ts is a datetime — serialize to ISO; ObjectIds in nested fields too.
        with AUDIT_FILE_FALLBACK.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
        record_id = f"file:{record['request_id']}"
        log.warning(
            "audit_log: Mongo unavailable; wrote to file fallback %s",
            AUDIT_FILE_FALLBACK,
        )
        return record_id
    except OSError as exc:  # pragma: no cover — fs paths
        log.error("audit_log file fallback failed: %s", exc)
        raise


def write_audit_log(
    action: str,
    tenant_id: str,
    request_id: str,
    **kwargs: Any,
) -> str:
    """Insert one schema-v1 ``audit_log`` row.

    Synchronous: returns only after insert is acknowledged. Real path
    uses pymongo + auditLogWriter role binding (ADR-0008 D3). File
    fallback is dev-only when Mongo is unreachable.

    Returns the inserted ``_id`` as a string.
    """
    if not tenant_id:
        raise ValueError("tenant_id required for audit_log insert (REQ-RAG-3)")
    if not request_id:
        raise ValueError("request_id required for audit_log insert (ADR-0008 D3)")

    # Outcome defaults to action-mirror if caller omitted; the real
    # endpoints pass it explicitly per spec §9.
    outcome = kwargs.pop("outcome", action)

    record = _build_record(
        action=action,
        tenant_id=tenant_id,
        request_id=request_id,
        outcome=outcome,
        **kwargs,
    )

    coll = _get_collection()
    if coll is None:
        return _write_file_fallback(record)

    try:
        result = coll.insert_one(record)
        return str(result.inserted_id)
    except PyMongoError as exc:
        log.error("audit_log mongo insert failed: %s", exc)
        # Spec §9: Mongo write failure → 503 in real path. Caller maps it.
        raise


def reset_for_tests() -> None:
    """Test-only — drops the cached MongoClient + collection."""
    global _mongo_client, _collection
    _mongo_client = None
    _collection = None
