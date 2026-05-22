"""
legacy_chain.py — pre-v1.0 LangChain LLMChain pattern.

⚠ DELIBERATE BROWNFIELD DEBT — Item 5 in docs/brownfield-debt.md ⚠

This module is the *intentional* pre-v1.0 LangChain code in the codebase.
The pattern below — `LLMChain(llm=llm, prompt=prompt); chain.run(input)` —
was the standard LangChain API up through 0.0.x and into 0.1.x. The v1.0+
preferred pattern is composed Runnables: `(prompt | llm | parser).invoke(...)`.

Cohort task in W2 Mon:
  - Identify all uses of LLMChain + .run() in the codebase
  - Rewrite as composed Runnables
  - Delete this module

The cohort sees BOTH styles in the same codebase (this file + the v1.0
endpoint in main.py) — which is the realistic migration state most
production codebases sit in mid-2026.

Note: we don't actually invoke the chain here (no real Bedrock creds in the
stub). The import + construction is enough for the cohort to find via grep
and identify as the legacy pattern.
"""
from __future__ import annotations

import logging
from typing import Any

# These imports work in langchain 0.3.x (transitional), but the LLMChain class
# is deprecated and the cohort migrates away in W2.
try:
    from langchain.chains import LLMChain          # ← pre-v1.0 pattern
    from langchain.prompts import PromptTemplate   # ← v0.x style
    _LEGACY_AVAILABLE = True
except ImportError:
    LLMChain = None  # type: ignore[assignment,misc]
    PromptTemplate = None  # type: ignore[assignment,misc]
    _LEGACY_AVAILABLE = False

log = logging.getLogger("ai-orchestrator.legacy_chain")


def draft_with_legacy_chain(topic: str, constraints: str | None, llm: Any) -> str:
    """
    ⚠ Item 5 — pre-v1.0 LangChain pattern. Cohort rewrites this in W2.

    The pattern:
        chain = LLMChain(llm=llm, prompt=prompt)
        result = chain.run(input=...)

    The v1.0 equivalent is:
        chain = prompt | llm | StrOutputParser()
        result = chain.invoke({"input": ...})
    """
    if not _LEGACY_AVAILABLE:
        raise RuntimeError("LLMChain not available — already on langchain v1.0+ only?")

    prompt = PromptTemplate(
        input_variables=["topic", "constraints"],
        template=(
            "You draft federal acquisition clauses. "
            "Draft a paragraph about: {topic}. Constraints: {constraints}."
        ),
    )

    # ↓↓↓ ITEM 5 — the legacy pattern. Cohort migrates to (prompt | llm | parser).
    chain = LLMChain(llm=llm, prompt=prompt)
    result = chain.run(topic=topic, constraints=constraints or "none")

    log.info("legacy_chain ran (Item 5 — to migrate in W2)")
    return result
