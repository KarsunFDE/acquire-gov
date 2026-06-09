"""M2 grounded retrieval — eval harness package.

Per docs/specs/m2-eval-harness.md. Each module is intentionally narrow:

- build_eval_set.py — corpus → eval-set generator (spec §3)
- judge.py         — Nova Micro judge wiring (spec §5)
- run_ragas.py     — RAGAS metric runner (spec §4)
- run_programmatic.py — Citation validity + cross-tenant fuzz + latency
                        (spec §6, three checks total — no others)
- ratchet.py       — One-directional threshold ratchet (spec §4.1)
"""
