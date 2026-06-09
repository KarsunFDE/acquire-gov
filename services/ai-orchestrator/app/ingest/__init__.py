"""Admin-side document ingest pipeline.

Internals for ``POST /ingest/document``. Wire shape locked in
``docs/specs/m2-retrieval-pipeline.md`` §4.3; per-stage behavior in
``docs/specs/m2-synthetic-corpus.md`` §8.

Submodules:
    loaders/         — format adapters (md, txt, pdf, json-prechunked)
    scanner          — chunk_quality_flag regex per ADR-0011 D1.1
"""
