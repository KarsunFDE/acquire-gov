"""
brownfield_debt_5 — locked-failing test.

Item 5 (docs/brownfield-debt.md#item-5): pre-v1.0 LangChain LLMChain +
.run() pattern lives in app/legacy_chain.py. Scheduled unlock: W2-Mon
when the cohort migrates to the LangChain v1.0 idiom — plain Python
composition (model.invoke(prompt.format(...))) for sequential flows
or create_agent(model, tools, middleware=[...]) for agentic flows —
and deletes the legacy file. Per LangChain v1.0 docs (Oct 2025), the
Chain class is removed and LCEL | pipe is no longer the central
composition pattern.

Convention: assertion = what-true-after-modernization.
While debt present -> legacy_chain.py exists AND contains LLMChain ->
test FAILS. When fix lands (file deleted, LLMChain references removed)
-> assertion passes -> CI flips lockfile.

See pipeline/T27-debt-enforcement-spec.md.
"""
from __future__ import annotations

from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent / "app"
LEGACY_CHAIN_FILE = APP_DIR / "legacy_chain.py"


@pytest.mark.brownfield_debt_5
def test_legacy_chain_file_deleted_DEBT_LOCKED() -> None:
    """When item 5 is modernized, app/legacy_chain.py is deleted."""
    assert not LEGACY_CHAIN_FILE.exists(), (
        f"Item 5 modernized — {LEGACY_CHAIN_FILE.relative_to(APP_DIR.parent)} "
        f"still exists. Migrate any LLMChain references to the LangChain v1.0 "
        f"idiom (plain Python: model.invoke(prompt.format(...)); agents via "
        f"create_agent(...)), delete the file, then update docs/debt-lockfile.yml "
        f"(flip locked: true -> false) and apply the debt-touch-approved label."
    )


@pytest.mark.brownfield_debt_5
def test_no_llmchain_references_in_app_DEBT_LOCKED() -> None:
    """When item 5 is modernized, no .py file under app/ imports or uses LLMChain."""
    offenders: list[str] = []
    for py_file in APP_DIR.rglob("*.py"):
        text = py_file.read_text()
        if "LLMChain" in text:
            offenders.append(str(py_file.relative_to(APP_DIR.parent)))
    assert offenders == [], (
        f"Item 5 modernized — LLMChain references remain in: {offenders}. "
        f"Migrate to LangChain v1.0 idiom (plain Python: model.invoke(prompt.format(...)); "
        f"agents via create_agent(...)) and remove LLMChain imports, then update "
        f"docs/debt-lockfile.yml + apply label. Per v1.0 docs, Chain class is removed; "
        f"LCEL | pipe is no longer central."
    )
