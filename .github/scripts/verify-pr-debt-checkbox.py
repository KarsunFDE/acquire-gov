#!/usr/bin/env python3
"""Cross-check PR body's debt-touch checkbox against lockfile diff + label state.

Reads env vars set by GHA:
  PR_BODY      — pull request body text
  PR_LABELS    — JSON array of {name: ...} label objects
  BASE_SHA     — base ref sha
  HEAD_SHA     — head ref sha

Rules:
  1. If PR diff includes docs/debt-lockfile.yml changes AND no `debt-touch-approved`
     label -> FAIL.
  2. If PR body's checkbox state is "YES" AND no lockfile diff -> FAIL.
  3. If PR body's checkbox state is "NO" AND lockfile diff exists -> FAIL.
  4. If PR body has neither NO nor YES checked -> FAIL (template not filled).

Spec: fde-10-week/pipeline/T27-debt-enforcement-spec.md
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

LOCKFILE_PATH = "docs/debt-lockfile.yml"
APPROVAL_LABEL = "debt-touch-approved"

# Format-tolerant: matches "- [x] NO", "* [x] **NO**", "- [X] No", etc. Bold
# markers and bullet char are optional — authors routinely hand-roll the body
# without the exact template markup, and the old bold-only pattern false-failed
# those legitimately-filled checkboxes. \b stops NONE / YESTERDAY false matches.
CHECKBOX_NO = re.compile(r"^\s*[-*]\s*\[x\]\s*\*{0,2}NO\b", re.MULTILINE | re.IGNORECASE)
CHECKBOX_YES = re.compile(r"^\s*[-*]\s*\[x\]\s*\*{0,2}YES\b", re.MULTILINE | re.IGNORECASE)


def fail(msg: str) -> None:
    print(f"::error::{msg}", file=sys.stderr)
    sys.exit(1)


def lockfile_changed(base_sha: str, head_sha: str) -> bool:
    if not base_sha or not head_sha:
        return False
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_sha}...{head_sha}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(f"::warning::git diff failed: {result.stderr}", file=sys.stderr)
        return False
    changed = result.stdout.strip().splitlines()
    return LOCKFILE_PATH in changed


def main() -> None:
    body = os.environ.get("PR_BODY", "") or ""
    labels_json = os.environ.get("PR_LABELS", "[]")
    base_sha = os.environ.get("BASE_SHA", "")
    head_sha = os.environ.get("HEAD_SHA", "")

    try:
        labels = [obj.get("name", "") for obj in json.loads(labels_json)]
    except json.JSONDecodeError as exc:
        fail(f"PR_LABELS not valid JSON: {exc}")

    has_approval_label = APPROVAL_LABEL in labels
    lockfile_diff = lockfile_changed(base_sha, head_sha)

    no_checked = bool(CHECKBOX_NO.search(body))
    yes_checked = bool(CHECKBOX_YES.search(body))

    if not no_checked and not yes_checked:
        fail(
            "PR template debt-touch checkbox not filled. Check exactly one — "
            "e.g. `- [x] NO` (default) or `- [x] YES` (then list item IDs)."
        )
    if no_checked and yes_checked:
        fail("Both NO and YES debt-touch checkboxes checked. Pick one.")

    if yes_checked and not lockfile_diff:
        fail(
            "PR template says YES (modernizing debt) but docs/debt-lockfile.yml "
            "has no changes. Update the lockfile to flip locked: true -> false "
            "for the touched items."
        )
    if no_checked and lockfile_diff:
        fail(
            "PR template says NO (not touching debt) but docs/debt-lockfile.yml "
            "has changes. Either change the checkbox to YES + list items, or "
            "revert the lockfile changes."
        )
    if lockfile_diff and not has_approval_label:
        fail(
            f"docs/debt-lockfile.yml mutated without the `{APPROVAL_LABEL}` "
            "label. Request the label from your instructor."
        )
    if has_approval_label and not lockfile_diff:
        fail(
            f"Label `{APPROVAL_LABEL}` applied but no lockfile diff present. "
            "Either update the lockfile or remove the label."
        )

    print("OK: PR template checkbox, lockfile diff, and approval label are consistent.")


if __name__ == "__main__":
    main()
