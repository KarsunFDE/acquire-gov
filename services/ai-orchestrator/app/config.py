"""M2 retrieval-pipeline configuration constants.

Source of truth: docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §10 + ADR-0010 D3.
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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


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

# ════════════════════════════════════════════════════════════════════════════
# M1 agentic drafting (ADR-0012/0013/0014/0015) — design ref §6, §18.6, §19
# ════════════════════════════════════════════════════════════════════════════

# --- Extractor model (ADR-0012 D2) ---

# Swapped Nova Lite → Haiku 4.5 (2026-06-15): more reliable structured output,
# fewer drafter retries; still cheap. (Was amazon.nova-lite-v1:0.)
BEDROCK_EXTRACT_MODEL = _env(
    "BEDROCK_EXTRACT_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
BEDROCK_EXTRACT_MAX_RETRIES = _env_int("BEDROCK_EXTRACT_MAX_RETRIES", 1)

# --- Drafter loop + output guards (DEMO-REDESIGN-spec §1 — cost-runaway guard) ---
# The expensive Sonnet drafter agents (section + part) previously ran at
# langchain 1.3.8's bound default recursion_limit of 9_999 (langgraph #7313) —
# the same unbounded surface that produced the 2.8M-token critic incident.
# Bound EVERY drafter invoke explicitly. recursion_limit counts SUPER-STEPS
# (each tool call = model turn + tool turn = 2), so the legit drafter sequence
# (retrieve→related→extract→gate→draft→validate→final, up to 6 tools) needs
# ~14-16. 25 = langgraph's own default — enough headroom for a valid multi-tool
# run, still far below a runaway (the critic incident hit 98). Env-tunable.
DRAFTER_RECURSION_LIMIT = _env_int("DRAFTER_RECURSION_LIMIT", 25)
# boto3/Bedrock transient-retry cap on every model client (retry-storm guard).
BEDROCK_MAX_RETRIES = _env_int("BEDROCK_MAX_RETRIES", 2)
# Per-model output-token caps (per-turn cost ceiling; defense-in-depth alongside
# recursion_limit). GEN covers the largest combined Part draft (C 6000 + H 1800).
BEDROCK_GEN_MAX_TOKENS = _env_int("BEDROCK_GEN_MAX_TOKENS", 8000)
BEDROCK_EXTRACT_MAX_TOKENS = _env_int("BEDROCK_EXTRACT_MAX_TOKENS", 2000)
BEDROCK_CRITIC_MAX_TOKENS = _env_int("BEDROCK_CRITIC_MAX_TOKENS", 2000)

# --- Boilerplate generator (D-G + K) — cheap model, single call, NO agent loop ---
# DEMO-REDESIGN-spec §2. D/E/F/G/K are near-verbatim FAR/GSAR clause text +
# solicitation specifics; a single with_structured_output() call (no tools, no
# agent) has zero recursion surface. Haiku for cost.
BEDROCK_BOILERPLATE_MODEL = _env(
    "BEDROCK_BOILERPLATE_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
BEDROCK_BOILERPLATE_MAX_TOKENS = _env_int("BEDROCK_BOILERPLATE_MAX_TOKENS", 1600)

# --- Stub mode (DEMO-REDESIGN-spec §0) — demo-day fallback while the Bedrock
# key is rolled. When true, ALL generation (agent drafters + boilerplate)
# returns canned, realistic content instead of calling Bedrock, so the full
# frontend flow works end-to-end with zero spend. Flip OFF once a live key is
# in .env. (Distinct from bedrock_client's legacy no-creds stub.)
AI_STUB_MODE = _env_bool("AI_STUB_MODE", False)

# --- Critic model (ADR-0013 D4) ---

# Swapped Nova Lite → Haiku 4.5 (2026-06-15): Nova Lite re-invoked the critic
# tools forever instead of emitting the final report (2026-06-12 incident).
# Haiku 4.5 actually completes the run. (Was amazon.nova-lite-v1:0.)
BEDROCK_CRITIC_MODEL = _env(
    "BEDROCK_CRITIC_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
# LangGraph recursion cap on critic agent invokes. With Nova Lite this was 3 to
# kill the runaway loop fast (accepting the skip-fallback). Haiku 4.5 completes
# legitimately, so the cap now allows a real 3-tool run: counts SUPER-STEPS
# (model+tool = 2 each), 3 tools sequential + final ≈ 8, so 10 with headroom —
# still bounds a runaway far below the 98-turn incident. Env-tunable.
CRITIC_RECURSION_LIMIT = _env_int("CRITIC_RECURSION_LIMIT", 10)
# True → extra clauses in Section K (beyond what the set-aside requires) raise
# warn. False (default Phase 1) → extras are info-only (ADR-0013 D5 note).
SET_ASIDE_STRICT_EXTRA = _env_bool("SET_ASIDE_STRICT_EXTRA", False)

# --- Gate thresholds (ADR-0012 D6; single source for tool AND middleware) ---

GATE_PASS_THRESHOLD = _env_float("GATE_PASS_THRESHOLD", 0.55)
GATE_WITHHOLD_THRESHOLD = _env_float("GATE_WITHHOLD_THRESHOLD", 0.40)

# --- Checkpointer (ADR-0012 D4) ---

AGENT_CHECKPOINT_COLLECTION = _env("AGENT_CHECKPOINT_COLLECTION", "agent_checkpoints")
AGENT_CHECKPOINT_WRITES_COLLECTION = _env(
    "AGENT_CHECKPOINT_WRITES_COLLECTION", "agent_checkpoint_writes"
)
# Explicit None — multi-day pause requirement; not env-readable (ADR-0012 D4).
AGENT_CHECKPOINT_TTL = None

# --- Orphan-thread sweeper (ADR-0012 D8.2) ---

AGENT_ORPHAN_SWEEP_INTERVAL_SECONDS = _env_int("AGENT_ORPHAN_SWEEP_INTERVAL_SECONDS", 3600)
AGENT_ORPHAN_AGE_DAYS = _env_int("AGENT_ORPHAN_AGE_DAYS", 30)

# --- Coordinator fan-out cap (ADR-0014 D9; was 4 under ADR-0013 D7.1) ---

MAX_BATCH_FAN_OUT = _env_int("MAX_BATCH_FAN_OUT", 2)

# --- LangSmith tracing (ADR-0012 D7) — all optional, disable gracefully ---

LANGSMITH_TRACING = _env_bool("LANGSMITH_TRACING", False)
LANGSMITH_API_KEY = os.environ.get("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = _env("LANGSMITH_PROJECT", "acquire-gov-m1-draft")
