"""M2 retrieval-pipeline configuration constants.

Source of truth: docs/specs/m2-retrieval-pipeline.md §10 + ADR-0010 D3.
Every constant below is pasted from the spec table. Env vars override at
process start; no per-request overrides except where explicitly allowed
(per-query RRF weights set by the query classifier in retrieval.py).

The legacy ``BEDROCK_MODEL_ID`` three-source drift (CLAUDE.md known issue)
is NOT consolidated here — that is W2 cohort modernization work.
``BEDROCK_GEN_MODEL`` below is the new M2 source of truth for the
generator; the legacy drift stays put until cohort week (ADR-0010 D3
note).
"""
from __future__ import annotations

import os


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# --- Bedrock models (ADR-0003, ADR-0005 D2, ADR-0007 D3, ADR-0009 D2) ---

BEDROCK_GEN_MODEL = _env(
    "BEDROCK_GEN_MODEL",
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
)
BEDROCK_EMBED_MODEL = _env("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0")
BEDROCK_EMBED_DIMS = _env_int("BEDROCK_EMBED_DIMS", 512)
BEDROCK_RERANK_MODEL_ARN = _env(
    "BEDROCK_RERANK_MODEL_ARN",
    "arn:aws:bedrock:us-west-2::foundation-model/amazon.rerank-v1:0",
)
BEDROCK_RERANK_REGION = _env("BEDROCK_RERANK_REGION", "us-west-2")
BEDROCK_JUDGE_MODEL = _env("BEDROCK_JUDGE_MODEL", "amazon.nova-micro-v1:0")

# --- Mongo (ADR-0005 D3, ADR-0008 D3/D5) ---

MONGO_URI = _env(
    "MONGO_URI",
    "mongodb://user:pass@mongodb:27017/?directConnection=true",
)
MONGO_DB = _env("MONGO_DB", "acquire_gov")
CHUNKS_COLLECTION = _env("CHUNKS_COLLECTION", "chunks")
AUDIT_LOG_COLLECTION = _env("AUDIT_LOG_COLLECTION", "audit_log")
VECTOR_INDEX_NAME = _env("VECTOR_INDEX_NAME", "far_vector_idx")
SEARCH_INDEX_NAME = _env("SEARCH_INDEX_NAME", "far_search_idx")

# --- Retrieval / rerank (ADR-0007 D2) ---

RETRIEVAL_K_CANDIDATES = _env_int("RETRIEVAL_K_CANDIDATES", 20)
RERANK_TOP_N = _env_int("RERANK_TOP_N", 5)
RERANK_WITHHOLD_THRESHOLD = _env_float("RERANK_WITHHOLD_THRESHOLD", 0.3)
RERANK_HITL_THRESHOLD = _env_float("RERANK_HITL_THRESHOLD", 0.5)

# --- Eval ratchet floors (ADR-0009 D1) ---

RAGAS_THRESHOLD_FAITHFULNESS = _env_float("RAGAS_THRESHOLD_FAITHFULNESS", 0.85)
RAGAS_THRESHOLD_ANSWER_RELEVANCY = _env_float("RAGAS_THRESHOLD_ANSWER_RELEVANCY", 0.80)
RAGAS_THRESHOLD_CONTEXT_PRECISION = _env_float("RAGAS_THRESHOLD_CONTEXT_PRECISION", 0.75)
RAGAS_THRESHOLD_CONTEXT_RECALL = _env_float("RAGAS_THRESHOLD_CONTEXT_RECALL", 0.80)

# --- Chunking (ADR-0006 D1) ---

CHUNK_SIZE = _env_int("CHUNK_SIZE", 1200)
CHUNK_OVERLAP = _env_int("CHUNK_OVERLAP", 150)

# --- Guardrails / rate limits (ADR-0011 D2, D4) ---

MAX_QUERY_CHARS = _env_int("MAX_QUERY_CHARS", 2000)
MAX_RESPONSE_CHARS = _env_int("MAX_RESPONSE_CHARS", 8000)
VECTOR_SEARCH_NUM_CANDIDATES = _env_int("VECTOR_SEARCH_NUM_CANDIDATES", 100)
RATE_LIMIT_QUERIES_PER_MINUTE_PER_TENANT = _env_int(
    "RATE_LIMIT_QUERIES_PER_MINUTE_PER_TENANT", 30
)
RATE_LIMIT_QUERIES_PER_DAY_PER_TENANT = _env_int(
    "RATE_LIMIT_QUERIES_PER_DAY_PER_TENANT", 1000
)

# --- AWS / region (ADR-0005 D2, ADR-0007 D3) ---

AWS_REGION = _env("AWS_REGION", "us-east-1")
AWS_BEARER_TOKEN_BEDROCK = os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
