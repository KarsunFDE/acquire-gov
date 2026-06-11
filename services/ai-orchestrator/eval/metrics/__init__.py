"""M1 eval-gate metrics (Phase 5 — RECORD-ONLY in Phase 1).

Seven metrics per design ref §13.2 + §18.8. None of these gate CI yet:
ADR-0013 D5 ships the critic warn-only because there is no precision
baseline — imposing recall floors before measuring precision contradicts
that rationale. A Phase 1.5 PR flips thresholds to gating after the first
baseline measurement.

Each module exposes a pure ``compute(...)`` over run records / fixtures so
the functions are unit-testable without Bedrock; ``eval.run_m1_metrics``
aggregates them into ``eval/results/m1_metrics.json`` + a markdown summary.
"""
