"""Per-run tool-call capture for the audit trail (ADR-0012 D9).

A LangChain callback handler that records one ``ToolCallRecord`` per tool
invocation inside an agent run. The handler is attached per-request via the
``callbacks`` entry of the agent's RunnableConfig, so records never bleed
across concurrent requests.

Only hashes of tool inputs/outputs are stored (ADR-0008 D3 — never raw text);
model/token fields are populated for LLM tools by parsing the tool's returned
Pydantic payload when present.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from pydantic import BaseModel, ConfigDict

log = logging.getLogger("ai-orchestrator.tool_call_capture")

_LLM_TOOLS = {"extract_section_requirements", "draft_section_text"}


class ToolCallRecord(BaseModel):
    """Audit sub-record per tool call (design ref §11)."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    tool_name: str
    started_at: datetime
    duration_ms: int
    input_hash: str
    output_hash: str | None = None
    model: str | None = None           # populated for LLM tools only
    input_tokens: int | None = None    # populated for LLM tools only
    output_tokens: int | None = None   # populated for LLM tools only
    error: str | None = None           # populated on raised tool
    degraded_flag: str | None = None   # e.g., "extract_degraded", "related_unavailable"


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class ToolCallCapture(BaseCallbackHandler):
    """Collects ToolCallRecord rows across one agent invocation."""

    def __init__(self) -> None:
        self.records: list[ToolCallRecord] = []
        self._in_flight: dict[UUID, tuple[str, datetime, str]] = {}

    # -- langchain callback surface ------------------------------------------

    def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, *, run_id: UUID, **kwargs: Any
    ) -> None:
        name = (serialized or {}).get("name", "unknown_tool")
        self._in_flight[run_id] = (
            name,
            datetime.now(timezone.utc),
            _sha256(input_str or ""),
        )

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._finish(run_id, output=output, error=None)

    def on_tool_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._finish(run_id, output=None, error=error)

    # -- internals -------------------------------------------------------------

    def _finish(self, run_id: UUID, *, output: Any, error: BaseException | None) -> None:
        entry = self._in_flight.pop(run_id, None)
        if entry is None:  # pragma: no cover — unmatched end
            return
        name, started_at, input_hash = entry
        now = datetime.now(timezone.utc)
        payload = _tool_payload(output)
        record = ToolCallRecord(
            tool_name=name,
            started_at=started_at,
            duration_ms=int((now - started_at).total_seconds() * 1000),
            input_hash=input_hash,
            output_hash=_sha256(str(output)) if output is not None else None,
            model=payload.get("model") if name in _LLM_TOOLS else None,
            input_tokens=payload.get("input_tokens") if name in _LLM_TOOLS else None,
            output_tokens=payload.get("output_tokens") if name in _LLM_TOOLS else None,
            error=str(error) if error else None,
            degraded_flag=_degraded_flag(name, payload),
        )
        self.records.append(record)


def _tool_payload(output: Any) -> dict:
    """Best-effort extraction of the tool's Pydantic payload fields."""
    target = output
    # ToolMessage wraps the artifact/content; unwrap common shapes.
    for attr in ("artifact", "content"):
        inner = getattr(output, attr, None)
        if isinstance(inner, BaseModel):
            target = inner
            break
    if isinstance(target, BaseModel):
        return target.model_dump()
    return {}


def _degraded_flag(name: str, payload: dict) -> str | None:
    if name == "extract_section_requirements" and payload.get("requirements") == [] and payload.get("source_text_hash"):
        return "extract_degraded"
    if name == "retrieve_far_clauses" and payload.get("degraded_mode"):
        return "degraded_vector_only"
    return None
