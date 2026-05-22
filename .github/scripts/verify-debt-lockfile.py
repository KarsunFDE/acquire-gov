#!/usr/bin/env python3
"""Verify docs/debt-lockfile.yml schema.

Run: python .github/scripts/verify-debt-lockfile.py docs/debt-lockfile.yml

Spec: fde-10-week/pipeline/T27-debt-enforcement-spec.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REQUIRED_FIELDS = {
    "id",
    "name",
    "locked",
    "scheduled_unlock_week",
    "test_marker",
    "test_path",
    "debt_doc_ref",
    "fixed_looks_like",
}
EXPECTED_ITEM_IDS = set(range(1, 13))
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def fail(msg: str) -> None:
    print(f"::error::{msg}", file=sys.stderr)
    sys.exit(1)


def main(lockfile_path: str) -> None:
    path = Path(lockfile_path)
    if not path.is_file():
        fail(f"Lockfile not found: {lockfile_path}")

    with path.open() as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        fail("Lockfile root must be a mapping")
    if data.get("version") != 1:
        fail(f"Unsupported lockfile version: {data.get('version')!r} (expected 1)")

    items = data.get("items")
    if not isinstance(items, list):
        fail("Lockfile `items` must be a list")

    seen_ids: set[int] = set()
    for raw_item in items:
        if not isinstance(raw_item, dict):
            fail(f"Item must be a mapping, got {type(raw_item).__name__}")
        missing = REQUIRED_FIELDS - raw_item.keys()
        if missing:
            fail(f"Item {raw_item.get('id', '?')} missing fields: {sorted(missing)}")
        item_id = raw_item["id"]
        if not isinstance(item_id, int):
            fail(f"Item id must be int, got {type(item_id).__name__}")
        if item_id in seen_ids:
            fail(f"Duplicate item id: {item_id}")
        seen_ids.add(item_id)
        if not isinstance(raw_item["locked"], bool):
            fail(f"Item {item_id} `locked` must be boolean")
        marker = raw_item["test_marker"]
        if marker != f"brownfield_debt_{item_id}":
            fail(
                f"Item {item_id} test_marker mismatch: got {marker!r}, "
                f"expected 'brownfield_debt_{item_id}'"
            )
        test_path = REPO_ROOT / raw_item["test_path"]
        if not test_path.exists():
            print(
                f"::warning::Item {item_id} test_path does not exist yet: "
                f"{raw_item['test_path']} (tests authored iter-12)"
            )

    if seen_ids != EXPECTED_ITEM_IDS:
        missing_ids = EXPECTED_ITEM_IDS - seen_ids
        extra_ids = seen_ids - EXPECTED_ITEM_IDS
        fail(
            f"Lockfile must contain exactly items 1-12. "
            f"Missing: {sorted(missing_ids)}, Extra: {sorted(extra_ids)}"
        )

    print(f"OK: lockfile schema valid; 12/12 items present; "
          f"{sum(1 for it in items if it['locked'])} locked.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        fail("Usage: verify-debt-lockfile.py <path-to-lockfile.yml>")
    main(sys.argv[1])
