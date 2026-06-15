"""Tool-schema compatibility shim for Bedrock Converse + Claude.

Anthropic's tool-schema validation (surfaced through Bedrock Converse as
``ValidationException: tools.N.custom: For 'integer' type, property
'minimum' is not supported``) rejects JSON Schema keywords that Pydantic
emits freely:

- numeric bounds (``minimum``/``maximum``/``exclusive*``/``multipleOf``)
  from ``Field(ge=..., le=...)`` — e.g. ``input_tokens: int = Field(ge=0)``
  on ``ExtractedRequirements``, which rides into ``draft_section_text``'s
  input schema;
- ``prefixItems`` from ``tuple[int, int]`` annotations (``source_span``,
  ``quote_span``).

The shim wraps ``langchain_aws...._format_tools`` once and strips/rewrites
those keywords in every toolSpec input schema. Enforcement is NOT lost:
the tool's pydantic ``args_schema`` still validates arguments at execution
time — the wire schema is advisory to the model.

Install via :func:`install` (idempotent); ``app.agents`` calls it at import
so every agent harness (section drafter, part drafters, critic) is covered.
"""
from __future__ import annotations

import functools
from typing import Any

_NUMERIC_BOUND_KEYS = (
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
)


def sanitize_json_schema(node: Any) -> None:
    """Recursively rewrite ``node`` in place to the Anthropic-supported subset."""
    if isinstance(node, dict):
        if node.get("type") in ("integer", "number"):
            for key in _NUMERIC_BOUND_KEYS:
                node.pop(key, None)
        prefix_items = node.pop("prefixItems", None)
        if prefix_items and "items" not in node:
            # tuple[T, ...] → plain typed array.
            node["items"] = prefix_items[0]
        # Anthropic allows minItems only as 0 or 1; maxItems mirrors it.
        if node.get("minItems") not in (None, 0, 1):
            node.pop("minItems", None)
        if node.get("maxItems") not in (None, 0, 1):
            node.pop("maxItems", None)
        for value in node.values():
            sanitize_json_schema(value)
    elif isinstance(node, list):
        for value in node:
            sanitize_json_schema(value)


_installed = False


def install() -> None:
    """Wrap ``_format_tools`` with the sanitizer. Idempotent."""
    global _installed
    if _installed:
        return
    from langchain_aws.chat_models import bedrock_converse as _bc

    original = _bc._format_tools

    @functools.wraps(original)
    def _format_tools_sanitized(tools: Any) -> Any:
        formatted = original(tools)
        for entry in formatted:
            schema = (
                entry.get("toolSpec", {}).get("inputSchema", {}).get("json")
                if isinstance(entry, dict)
                else None
            )
            if schema:
                sanitize_json_schema(schema)
        return formatted

    _bc._format_tools = _format_tools_sanitized
    _installed = True
