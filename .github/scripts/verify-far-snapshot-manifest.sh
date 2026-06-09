#!/usr/bin/env bash
# verify-far-snapshot-manifest.sh — assert docs/reference/far/MANIFEST.sha256
# matches the on-disk bytes of every far-part-*.md sibling.
#
# Spec: docs/specs/m2-retrieval-pipeline.md §10 corpus integrity;
# ADR-0005 D5 snapshot pinning; ADR-0006 D1 markdown header convention.
#
# Exits 1 on any mismatch (missing file, hash drift, file present but unlisted).
# CRLF drift is the prior failure mode (commit 4c92749) — the MANIFEST is
# generated with explicit LF newlines; this verifier hashes bytes verbatim,
# so any CRLF conversion in transit will trip the mismatch.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FAR_DIR="$REPO_ROOT/docs/reference/far"
MANIFEST="$FAR_DIR/MANIFEST.sha256"

if [ ! -f "$MANIFEST" ]; then
    echo "::error::MANIFEST.sha256 missing at $MANIFEST" >&2
    exit 1
fi

cd "$FAR_DIR"

# sha256sum -c reads "<sha>  <relpath>" lines and verifies. Mismatch → non-zero.
if ! sha256sum -c MANIFEST.sha256; then
    echo "::error::FAR snapshot hash mismatch — regenerate MANIFEST.sha256 or restore files" >&2
    exit 1
fi

# Detect files present on disk but not in MANIFEST — append-only is a corpus
# invariant; silently-added FAR files would bypass the synthetic-data CI gate.
listed=$(awk '{print $2}' MANIFEST.sha256 | sort)
present=$(find . -maxdepth 1 -name 'far-part-*.md' -printf '%f\n' | sort)
unlisted=$(comm -23 <(echo "$present") <(echo "$listed") || true)

if [ -n "$unlisted" ]; then
    echo "::error::FAR file(s) present on disk but absent from MANIFEST.sha256:" >&2
    echo "$unlisted" >&2
    exit 1
fi

echo "OK: FAR snapshot manifest verified."
