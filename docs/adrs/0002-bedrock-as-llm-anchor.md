# ADR 0002 — AWS Bedrock as the LLM anchor

Date: 2025-Q3 (predates the cohort)
Status: Accepted (legacy)
Decision-makers: Original instructor authoring team

## Context

The cohort needs a single LLM provider as the programme default so they're not learning N provider SDKs simultaneously. Karsun's actual production AI runs on AWS Bedrock; their ReDuX product is Bedrock-powered (public material). Federal context requires GovCloud-awareness — Bedrock has FedRAMP High authorization in GovCloud regions.

## Decision

AWS Bedrock with Claude (Anthropic) as the programme-default LLM. Cross-region inference enabled for higher throughput. Alternatives — OpenAI direct, Azure OpenAI, self-hosted — surface as **scenario-alternatives prompts** so the cohort defends the choice instead of taking it for granted.

## Alternatives considered

1. **OpenAI direct API.** Surfaces as a scenario-alternatives prompt (W1 Fri / W2 Mon constraint variant). Federal-context FedRAMP gap is the defending argument against.
2. **Azure OpenAI.** Surfaces as a scenario-alternatives variant for cohorts on Azure-mandate constraints.
3. **Self-hosted (Llama, Mistral).** Surfaces in W4 brownfield modernization week as a "what if FedRAMP wasn't an issue" thought experiment.

## Consequences

- Cohort needs AWS Bedrock model-access verification on W1 Tue (item 6 of W1 Tue topic list).
- Bedrock model invocation patterns (W1 Thu) are the production anchor; OpenAI patterns become alternative-tech material.
- Cross-region inference + cost-per-token + streaming all teachable on Bedrock.

## Rollback story

If a future cohort lands at a client that mandates a different LLM (Azure OpenAI for a specific federal contract, e.g.), the programme can switch by updating ADR-0002 and `services/ai-orchestrator/` for cohort #2. Not mid-cohort.
