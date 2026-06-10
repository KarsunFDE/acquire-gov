"""RAGAS judge model wiring — Nova Micro via LiteLLM (eval-only).

Per docs/specs/m2-grounded-retrieval/eval-harness.md section 5 + ADR-0009 D2. This file is the
ONLY place in the repo allowed to instantiate the Nova Micro client.
Containment is enforced by CI grep in .github/workflows/rag-eval-gate.yml:

    Anti-pattern #1 (ADR-0009 D5) — judge != generator.
    This file MUST NOT reference the generator model identifier. The CI
    step `grep -r "claude-sonnet" eval/judge.py` MUST return non-zero
    matches → empty → job passes.

Auth reuses AWS_BEARER_TOKEN_BEDROCK from the generator path (boto3 1.39.11
floor — see requirements.txt). No new credential surface.
"""
from __future__ import annotations

import os

# Judge model ID — pinned per ADR-0009 D2.
# Format string deliberately split: keeps grep simple-substring checks
# (CI greps for the generator family name; this file must contain none).
JUDGE_MODEL_ID = "amazon.nova-micro-v1:0"
JUDGE_LITELLM_PATH = f"bedrock/{JUDGE_MODEL_ID}"
JUDGE_TEMPERATURE = 0.0  # spec section 5.2: deterministic judge output


def build_judge_llm():
    """Return the RAGAS-wrapped judge LLM.

    Verbatim wiring from ADR-0009 D2:

        from ragas.llms import llm_factory
        import litellm
        judge_llm = llm_factory(
            "bedrock/amazon.nova-micro-v1:0",
            provider="litellm",
            client=litellm.completion,
            temperature=0.0,
        )

    Imports happen inside the function so unit tests that don't need a live
    judge (e.g. ratchet logic, build_eval_set) don't pay the ragas+litellm
    import cost or require the deps to be installed.
    """
    # Late imports — these are heavy. Production CI installs ragas + litellm
    # via requirements.txt; local dev without them still imports this module.
    from ragas.llms import llm_factory  # type: ignore[import-not-found]
    import litellm  # type: ignore[import-not-found]

    return llm_factory(
        JUDGE_LITELLM_PATH,
        provider="litellm",
        client=litellm.completion,
        temperature=JUDGE_TEMPERATURE,
    )


def assert_bedrock_auth_present() -> None:
    """Spec section 5.2 containment rule 3: same AWS_BEARER_TOKEN_BEDROCK as generator.

    Fails fast in CI rather than letting the judge silently fall back to
    no-auth. Caller (run_ragas.py) invokes this once at startup.
    """
    if not os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
        # Allow IAM key-pair fallback (CLAUDE.md D-060 — boto3 still resolves
        # AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY via the default chain).
        if not (
            os.environ.get("AWS_ACCESS_KEY_ID")
            and os.environ.get("AWS_SECRET_ACCESS_KEY")
        ):
            raise RuntimeError(
                "Judge requires AWS_BEARER_TOKEN_BEDROCK (preferred) or AWS_ACCESS_KEY_ID "
                "+ AWS_SECRET_ACCESS_KEY (IAM fallback). Spec section 5.2 / CLAUDE.md D-060."
            )
