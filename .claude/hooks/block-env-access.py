#!/usr/bin/env python3
"""PreToolUse hook: block any tool call that targets a .env file.

Reads the standard Claude Code hook JSON payload from stdin. Exits 2 with
a stderr message when blocking, which Claude Code surfaces to the model
and refuses the tool call. Allows .env.example (it is the template).
"""
from __future__ import annotations

import json
import re
import sys


def _basename(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].lower()


def is_env_path(path: str) -> bool:
    if not path:
        return False
    base = _basename(path)
    if base == ".env.example" or base.endswith(".example"):
        return False
    return base == ".env" or base.startswith(".env.")


# Match .env tokens in shell commands. Negative lookahead skips .env.example
# and .env.sample-style templates.
_BASH_ENV_RE = re.compile(
    r"(?<![A-Za-z0-9_.\-/\\])\.env(?:\.[A-Za-z0-9_.\-]+)?(?![A-Za-z0-9_.\-])"
)
_TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".tmpl", ".dist")


def bash_touches_env(command: str) -> bool:
    if not command:
        return False
    for match in _BASH_ENV_RE.finditer(command):
        token = match.group(0).lower()
        if token == ".env":
            return True
        if any(token.endswith(s) for s in _TEMPLATE_SUFFIXES):
            continue
        return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input", {}) or {}

    blocked: str | None = None

    if tool in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = inp.get("file_path") or inp.get("notebook_path") or ""
        if is_env_path(path):
            blocked = (
                f"Blocked by .claude/hooks/block-env-access.py: tool '{tool}' "
                f"targeted '{path}'. .env files are off-limits — use "
                ".env.example for templates or ask the user for the value."
            )

    elif tool == "Bash":
        if bash_touches_env(inp.get("command", "")):
            blocked = (
                "Blocked by .claude/hooks/block-env-access.py: shell command "
                "references a .env file. Read .env.example instead, or ask "
                "the user to surface the specific value you need."
            )

    elif tool == "Grep":
        path = inp.get("path", "")
        if is_env_path(path):
            blocked = (
                "Blocked by .claude/hooks/block-env-access.py: Grep path "
                "targets a .env file."
            )

    elif tool == "Glob":
        pattern = (inp.get("pattern") or "").strip().lower()
        # only block patterns that explicitly enumerate .env files
        if pattern in {".env", ".env*", "**/.env", "**/.env*", "./.env", "./.env*"}:
            blocked = (
                "Blocked by .claude/hooks/block-env-access.py: Glob pattern "
                f"'{pattern}' enumerates .env files."
            )

    if blocked:
        print(blocked, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
