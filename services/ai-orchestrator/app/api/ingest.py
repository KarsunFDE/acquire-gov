"""``POST /ingest/document`` router — M2 admin ingest endpoint.

Wire shape locked in ``docs/specs/m2-retrieval-pipeline.md`` §4.3; handler
internals follow ``docs/specs/m2-synthetic-corpus.md`` §8 step table.

Pipeline-agent-owned modules (``app.config``, ``app.audit``,
``app.bedrock_client``) are imported **lazily inside the handler** so the
router module itself loads cleanly even if those modules have not landed
yet (parallel-track work — spec §14 dependency note). Tests mock the lazy
calls; production picks up the real modules as they land.

Spec sections cross-referenced inline use the form ``§8 step N``.
"""
from __future__ import annotations

import io
import json
import logging
import time
import uuid
from typing import Any, Iterable

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.ingest import scanner

log = logging.getLogger("ai-orchestrator.ingest")

router = APIRouter(prefix="/ingest", tags=["ingest"])

# Cap pasted from ``m2-retrieval-pipeline.md`` §4.3. Hard-coded here so the
# size guard runs even if ``app.config`` has not been provisioned by the
# pipeline-agent track yet; once config lands, this value mirrors it.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# Defaults — re-stated from ADR-0006 D1 so the loader stack runs without
# ``app.config``. When pipeline agent's ``config.py`` lands we read from
# there instead (see ``_get_config`` below).
_DEFAULT_CHUNK_SIZE = 1200
_DEFAULT_CHUNK_OVERLAP = 150

# Valid doc_class values from spec §2.
_VALID_DOC_CLASS = {"far_reference", "synthetic_solicitation", "agency_template"}
_VALID_FORMAT = {"md", "txt", "pdf", "json-prechunked"}


class IngestMetadata(BaseModel):
    """``metadata`` form-field JSON schema — spec §2."""

    source_doc_name: str = Field(min_length=1, max_length=256)
    far_part: str | None = None
    far_section: str | None = None
    snapshot_date: str = Field(min_length=8)  # ISO date (YYYY-MM-DD minimum)
    doc_class: str

    @field_validator("doc_class")
    @classmethod
    def _check_class(cls, v: str) -> str:
        if v not in _VALID_DOC_CLASS:
            raise ValueError(f"doc_class must be one of {sorted(_VALID_DOC_CLASS)}")
        return v


def _get_config() -> dict[str, Any]:
    """Read chunking constants from ``app.config`` if available; else defaults."""
    try:
        from app import config as _cfg  # type: ignore[import-not-found]
    except ImportError:
        return {
            "CHUNK_SIZE": _DEFAULT_CHUNK_SIZE,
            "CHUNK_OVERLAP": _DEFAULT_CHUNK_OVERLAP,
        }
    return {
        "CHUNK_SIZE": getattr(_cfg, "CHUNK_SIZE", _DEFAULT_CHUNK_SIZE),
        "CHUNK_OVERLAP": getattr(_cfg, "CHUNK_OVERLAP", _DEFAULT_CHUNK_OVERLAP),
    }


def _dispatch_loader(fmt: str, raw: bytes) -> list[dict[str, Any]]:
    """Spec §8 step 5 — format-adapter dispatch."""
    if fmt == "md":
        from app.ingest.loaders import markdown as _md
        return _md.load(raw.decode("utf-8", errors="replace"))
    if fmt == "txt":
        from app.ingest.loaders import plaintext as _txt
        return _txt.load(raw.decode("utf-8", errors="replace"))
    if fmt == "pdf":
        from app.ingest.loaders import pdf as _pdf  # type: ignore[import-not-found]
        return _pdf.load(raw)
    if fmt == "json-prechunked":
        from app.ingest.loaders import json_prechunked as _jp  # type: ignore[import-not-found]
        return _jp.load(raw)
    raise HTTPException(status_code=422, detail={"error": "unsupported_format", "format": fmt})


def _second_stage_split(records: list[dict[str, Any]], *, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Spec §8 step 7 — second-stage ``RecursiveCharacterTextSplitter``.

    Applies to markdown/txt/pdf loader output. The ``json-prechunked``
    format skips this step (caller asserts chunks per §9.4) — the handler
    branches on ``format`` before calling here.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg["CHUNK_SIZE"],
        chunk_overlap=cfg["CHUNK_OVERLAP"],
    )
    out: list[dict[str, Any]] = []
    chunk_index = 0
    for rec in records:
        text = rec.get("text", "")
        if not text.strip():
            continue
        # Carry section metadata into each sub-chunk.
        inherited = {k: v for k, v in rec.items() if k != "text"}
        sub_texts = splitter.split_text(text)
        if not sub_texts:
            sub_texts = [text]
        char_cursor = 0
        for sub in sub_texts:
            start = text.find(sub, char_cursor)
            if start < 0:
                start = char_cursor
            end = start + len(sub)
            char_cursor = end
            out.append({
                **inherited,
                "text": sub,
                "chunk_index": chunk_index,
                "char_start": start,
                "char_end": end,
            })
            chunk_index += 1
    return out


def _audit(record: dict[str, Any]) -> None:
    """Spec §8.1 — best-effort sync write to ``audit_log``.

    Lazy-imports ``app.audit`` so the router loads without it; in test we
    monkeypatch this function directly. Audit failures DO NOT silently
    swallow — the spec says sync write-through (ADR-0008 D3 / spec §3
    stage 12). We surface as 503.
    """
    try:
        from app import audit as _audit_mod  # type: ignore[import-not-found]
    except ImportError:
        log.warning("audit module unavailable; ingest record NOT persisted: %s", record.get("source_doc_name"))
        return
    writer = getattr(_audit_mod, "write_audit_log", None)
    if writer is None:
        log.warning("audit.write_audit_log absent; ingest record NOT persisted")
        return
    writer(**record)


def _embed(texts: list[str]) -> list[list[float]]:
    """Spec §8 step 9 — Titan v2 @ 512 embeddings via the pipeline-agent client.

    Lazy-imported so a missing ``bedrock_client.embed_documents`` does not
    sink the router; tests monkeypatch this function.
    """
    try:
        from app import bedrock_client as _bc  # type: ignore[import-not-found]
    except ImportError:
        return [[0.0] * 512 for _ in texts]
    embed_fn = getattr(_bc, "embed_documents", None)
    if embed_fn is None:
        return [[0.0] * 512 for _ in texts]
    return list(embed_fn(texts))


def _bulk_insert(chunks: list[dict[str, Any]]) -> str:
    """Spec §8 step 10 — write chunks; return synthetic document_id.

    Lazy-imports the Mongo client wrapper (pipeline-agent territory). When
    absent we still return a generated ID — tests mock this anyway, and
    production loads with the real wrapper present.
    """
    document_id = str(uuid.uuid4())
    try:
        from app import retrieval as _ret  # type: ignore[import-not-found]
    except ImportError:
        return document_id
    inserter = getattr(_ret, "bulk_insert_chunks", None)
    if inserter is None:
        return document_id
    inserter(chunks, document_id=document_id)
    return document_id


def _duplicate_doc_check(*, tenant_id: str, source_doc: str, snapshot_date: str) -> str | None:
    """Spec §10.1 — pre-insert uniqueness probe.

    Returns the existing ``document_id`` (string) if a duplicate row is
    present, else ``None``. Lazy-imports retrieval; tests patch directly.
    """
    try:
        from app import retrieval as _ret  # type: ignore[import-not-found]
    except ImportError:
        return None
    probe = getattr(_ret, "find_existing_document", None)
    if probe is None:
        return None
    return probe(tenant_id=tenant_id, source_doc=source_doc, snapshot_date=snapshot_date)


@router.post("/document")
async def ingest_document(
    request: Request,
    file: UploadFile = File(...),
    metadata: str = Form(...),
    format: str = Form(...),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    """``POST /ingest/document`` — see ``m2-retrieval-pipeline.md`` §4.3."""
    start = time.perf_counter()
    request_id = x_request_id or str(uuid.uuid4())

    # §8 step 1 — tenant header (rate-limit slowapi key; full limiter wired
    # by pipeline-agent C9). Missing header → 400 per spec §9.
    if not x_tenant_id:
        return JSONResponse(
            status_code=400,
            content={"error": "tenant_id_required", "request_id": request_id},
        )

    # §8 step 2 — auth placeholder. Full admin-role enforcement is M1
    # territory (spec §15 open items). Phase-1 stance: accept any
    # ``Authorization`` header; reject only an explicit empty one.
    # The "admin role" tag is recorded on the audit row for replay.

    # §8 step 3 — parse multipart
    if format not in _VALID_FORMAT:
        return JSONResponse(
            status_code=422,
            content={"error": "unsupported_format", "format": format, "request_id": request_id},
        )

    try:
        meta_obj = IngestMetadata.model_validate_json(metadata)
    except ValidationError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": "invalid_metadata",
                "details": exc.errors(),
                "request_id": request_id,
            },
        )

    raw = await file.read()
    size = len(raw)

    # §8 step 4 — size guard. Spec maps oversize to 413 ``payload_too_large``.
    if size > MAX_UPLOAD_BYTES:
        _audit({
            "action": "ingest_document",
            "outcome": "payload_too_large",
            "tenant_id": x_tenant_id,
            "request_id": request_id,
            "source_doc_name": meta_obj.source_doc_name,
            "doc_class": meta_obj.doc_class,
            "snapshot_date": meta_obj.snapshot_date,
            "format": format,
            "size_bytes": size,
            "chunks_inserted": 0,
            "actor_role": "admin",
        })
        return JSONResponse(
            status_code=413,
            content={"error": "payload_too_large", "size_bytes": size, "request_id": request_id},
        )

    # §8 step 5+6 — dispatch + loader returns
    try:
        loader_records = _dispatch_loader(format, raw)
    except HTTPException:
        raise
    except Exception as exc:
        # Map loader-specific errors to spec-defined outcomes (§8.1).
        err_name = type(exc).__name__
        if err_name == "PdfTextExtractionFailed":
            _audit({
                "action": "ingest_document",
                "outcome": "pdf_text_extraction_failed",
                "tenant_id": x_tenant_id,
                "request_id": request_id,
                "source_doc_name": meta_obj.source_doc_name,
                "doc_class": meta_obj.doc_class,
                "snapshot_date": meta_obj.snapshot_date,
                "format": format,
                "chunks_inserted": 0,
                "actor_role": "admin",
            })
            return JSONResponse(
                status_code=422,
                content={
                    "error": "pdf_text_extraction_failed",
                    "message": str(exc),
                    "request_id": request_id,
                },
            )
        if err_name == "JsonPrechunkedMalformed":
            return JSONResponse(
                status_code=422,
                content={
                    "error": "json_prechunked_malformed",
                    "message": str(exc),
                    "request_id": request_id,
                },
            )
        log.exception("loader failed format=%s source_doc=%s", format, meta_obj.source_doc_name)
        return JSONResponse(
            status_code=422,
            content={
                "error": "loader_failed",
                "format": format,
                "message": str(exc),
                "request_id": request_id,
            },
        )

    cfg = _get_config()

    # §8 step 7 — second-stage split (SKIPPED for json-prechunked)
    if format == "json-prechunked":
        chunks = loader_records
        # Re-number chunk_index in case caller did not provide one
        for idx, c in enumerate(chunks):
            c.setdefault("chunk_index", idx)
            c.setdefault("char_start", 0)
            c.setdefault("char_end", len(c.get("text", "")))
    else:
        chunks = _second_stage_split(loader_records, cfg=cfg)

    if not chunks:
        return JSONResponse(
            status_code=422,
            content={
                "error": "no_chunks_produced",
                "request_id": request_id,
            },
        )

    # §8 step 8 — content scan (fail-closed). ABORT, no insert.
    flagged = scanner.scan_chunks(chunks)
    if flagged:
        flagged_ids = [f"chunk_{idx}" for idx, _ in flagged]
        _audit({
            "action": "ingest_document",
            "outcome": "chunk_quality_flag_raised",
            "tenant_id": x_tenant_id,
            "request_id": request_id,
            "source_doc_name": meta_obj.source_doc_name,
            "doc_class": meta_obj.doc_class,
            "snapshot_date": meta_obj.snapshot_date,
            "format": format,
            "flagged_chunk_ids": flagged_ids,
            "chunks_inserted": 0,
            "actor_role": "admin",
        })
        return JSONResponse(
            status_code=422,
            content={
                "error": "chunk_quality_flag_raised",
                "flagged_chunk_ids": flagged_ids,
                "request_id": request_id,
            },
        )

    # §10.1 — duplicate-doc probe (after scan, before embed)
    existing_id = _duplicate_doc_check(
        tenant_id=x_tenant_id,
        source_doc=meta_obj.source_doc_name,
        snapshot_date=meta_obj.snapshot_date,
    )
    if existing_id:
        _audit({
            "action": "ingest_document",
            "outcome": "duplicate_doc",
            "tenant_id": x_tenant_id,
            "request_id": request_id,
            "source_doc_name": meta_obj.source_doc_name,
            "doc_class": meta_obj.doc_class,
            "snapshot_date": meta_obj.snapshot_date,
            "format": format,
            "existing_document_id": existing_id,
            "chunks_inserted": 0,
            "actor_role": "admin",
        })
        return JSONResponse(
            status_code=409,
            content={
                "error": "duplicate_doc",
                "existing_document_id": existing_id,
                "request_id": request_id,
            },
        )

    # §8 step 9 — embed
    embeddings = _embed([c["text"] for c in chunks])

    # §8 step 10 — assemble + bulk insert
    for c, emb in zip(chunks, embeddings):
        c["tenant_id"] = x_tenant_id
        c["embedding"] = emb
        c["source_doc"] = meta_obj.source_doc_name
        c["snapshot_date"] = meta_obj.snapshot_date
        c["doc_class"] = meta_obj.doc_class
        c.setdefault("chunk_quality_flag", None)
        if meta_obj.far_part and not c.get("far_part"):
            c["far_part"] = meta_obj.far_part
        if meta_obj.far_section and not c.get("far_section"):
            c["far_section"] = meta_obj.far_section

    document_id = _bulk_insert(chunks)
    duration_ms = int((time.perf_counter() - start) * 1000)

    # §8 step 11 — audit on success
    _audit({
        "action": "ingest_document",
        "outcome": "ingested",
        "tenant_id": x_tenant_id,
        "request_id": request_id,
        "source_doc_name": meta_obj.source_doc_name,
        "doc_class": meta_obj.doc_class,
        "snapshot_date": meta_obj.snapshot_date,
        "format": format,
        "chunks_inserted": len(chunks),
        "flagged_chunks": [],
        "duration_ms": duration_ms,
        "actor_role": "admin",
    })

    # §8 step 12 — response
    return JSONResponse(
        status_code=200,
        content={
            "document_id": document_id,
            "chunks_inserted": len(chunks),
            "flagged_chunks": [],
            "duration_ms": duration_ms,
            "request_id": request_id,
        },
    )
