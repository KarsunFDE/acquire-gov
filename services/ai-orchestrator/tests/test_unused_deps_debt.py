"""
brownfield_debt_7 — locked-failing test.

Item 7 (docs/brownfield-debt.md#item-7): pinecone-client is listed in
requirements.txt but no code imports it. Scheduled unlock: W2-Mon when
Atlas Vector Search work begins.

Convention: assertion = what-true-after-modernization.
While debt present -> pinecone-client IS in requirements -> test FAILS.
When fix lands (line removed) -> assertion passes -> CI flips lockfile.

See pipeline/T27-debt-enforcement-spec.md.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REQUIREMENTS = (
    Path(__file__).resolve().parent.parent / "requirements.txt"
)


@pytest.mark.brownfield_debt_7
def test_pinecone_client_removed_from_requirements_DEBT_LOCKED() -> None:
    """When item 7 is modernized, pinecone-client is removed from requirements.txt."""
    text = REQUIREMENTS.read_text()
    non_comment_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    pinecone_lines = [line for line in non_comment_lines if "pinecone" in line.lower()]
    assert pinecone_lines == [], (
        f"Item 7 modernized — pinecone-client found in requirements.txt: "
        f"{pinecone_lines}. Update docs/debt-lockfile.yml (flip locked: true -> "
        f"false) and apply the debt-touch-approved label."
    )
