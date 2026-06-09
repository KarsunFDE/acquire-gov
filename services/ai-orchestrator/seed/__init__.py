"""Seed scripts for the M2 corpus.

Modules:
    build_synthetic_solicitations — pure-template generator for the 10
        synthetic solicitations in ``docs/reference/synthetic-solicitations/``
        (spec §7). NO LLM calls — anti-pattern #13 (ADR-0009 D5) bars
        LLM-generated eval ground truth.
    run_seed — orchestrates FAR snapshot ingest + synthetic solicitation
        ingest (spec §11).
"""
