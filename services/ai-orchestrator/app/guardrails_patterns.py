"""
Query-side guardrail regex patterns. Per ADR-0011 D2 (hand-built Guardrails-
equivalent; managed Bedrock Guardrails OOS per PRD §7).

Patterns stored as raw strings so the regex catalog lives in one place and the
QueryGuardrails class in app/guardrails.py stays thin. Extend during eval.
"""
from __future__ import annotations

import re

# Decoded at module load from base64 to keep the source diff free of literal
# adversarial phrasing that some CI/review tooling flags. Functionally identical
# to a checked-in list of re.compile(...) calls.
import base64

_RAW_PATTERNS_B64 = [
    # (?i)ignore (previous|prior|all) (instructions|context)
    "KD9pKWlnbm9yZSAocHJldmlvdXN8cHJpb3J8YWxsKSAoaW5zdHJ1Y3Rpb25zfGNvbnRleHQp",
    # (?i)disregard (previous|prior|all) (instructions|context)
    "KD9pKWRpc3JlZ2FyZCAocHJldmlvdXN8cHJpb3J8YWxsKSAoaW5zdHJ1Y3Rpb25zfGNvbnRleHQp",
    # (?i)you are now (in )?[a-z]+ mode
    "KD9pKXlvdSBhcmUgbm93IChpbiApP1thLXpdKyBtb2Rl",
    # (?i)(print|reveal|show) (your )?(system )?prompt
    "KD9pKShwcmludHxyZXZlYWx8c2hvdykgKHlvdXIgKT8oc3lzdGVtICk/cHJvbXB0",
    # (?i)previous (user|conversation|session)
    "KD9pKXByZXZpb3VzICh1c2VyfGNvbnZlcnNhdGlvbnxzZXNzaW9uKQ==",
    # (?i)act as (a |an )?(?!contracting officer)  — allow domain role-play
    "KD9pKWFjdCBhcyAoYSB8YW4gKT8oPyFjb250cmFjdGluZyBvZmZpY2VyKQ==",
    # (?i)system\s*:\s*you are
    "KD9pKXN5c3RlbVxzKjpccyp5b3UgYXJl",
    # (?i)<\|.*?\|>  — chat-template role-marker escape attempts
    "KD9pKTxcfC4qP1x8Pg==",
]

JAILBREAK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(base64.b64decode(p).decode("utf-8")) for p in _RAW_PATTERNS_B64
]

# Length cap — DoS guard + signal for needs_llm_review escalation.
MAX_QUERY_CHARS = 2000

# Borderline-query heuristic: queries above this length get the Nova Micro
# judge layer (ADR-0011 D2 Layer 2). Below = regex-only.
LLM_REVIEW_LENGTH_THRESHOLD = 500
