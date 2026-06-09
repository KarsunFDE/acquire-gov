"""Format adapters for ``POST /ingest/document``.

Each loader returns a list of pre-second-stage chunk dicts shaped per
ADR-0006 D2. The handler in ``app/api/ingest.py`` runs the second-stage
``RecursiveCharacterTextSplitter`` over the loader output (skipped for
``json-prechunked`` — caller asserts chunks per spec §9.4).
"""
from __future__ import annotations

# Per-loader modules are imported lazily by the dispatch table in
# ``app/api/ingest.py`` to keep optional deps (pypdf) out of the import
# graph until used.
