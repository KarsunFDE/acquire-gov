# ADR 0001 — Microservices architecture

Date: 2025-Q3 (predates the cohort)
Status: Accepted (legacy)
Decision-makers: Original instructor authoring team

## Context

The training project needs to mirror how Karsun's federal acquisitions engagements actually deploy so the cohort encounters real architectural patterns. Karsun's open Senior Full Stack Developer + Angular Developer roles disclose: Java/JEE/Spring Boot service tier + Angular SPA + AWS deployment. The federal context also implies multi-tenant data isolation and OIG-grade audit trails.

## Decision

Adopt a microservices architecture from Day 1:

- **Angular SPA** at the edge (contracting-officer UX).
- **API Gateway** (Spring Boot) for auth-edge + routing.
- **Solicitation Service** (Spring Boot) for FAR/DFARS solicitation lifecycle.
- **Evaluation Service** (Spring Boot) for evaluation-panel coordination.
- **AI Orchestrator** (Python/FastAPI) for LLM/RAG/agent work — sits *behind* Spring Boot so the cohort sees realistic service-mesh patterns.

Inter-service communication uses sync REST for read paths + async messaging where deliberate (TBD which queue — see future ADR).

## Alternatives considered

1. **Monolithic Spring Boot.** Rejected — doesn't reflect Karsun's actual production shape; the cohort wouldn't get exposure to service-boundary thinking.
2. **All-Python stack.** Rejected — Karsun's Java disclosure makes Spring Boot the necessary service-tier teaching surface.
3. **Serverless Lambda mesh.** Rejected for cohort #1 — too many concurrent new concepts; revisit for cohort #2 as an alternative-tech scenario.

## Consequences

- W1 Tue gets a real microservices walkthrough surface.
- The brownfield debt list is richer (each service has its own legacy debt).
- Docker Compose orchestration becomes a Day-1 cohort prerequisite.
- **Known weakness:** the boundary between solicitation-service and evaluation-service is *deliberately under-defined* — the cohort discovers it as a refactor target.

## Rollback story

This is a foundational decision. Rolling back means rewriting the whole scaffold. **Not rollback-able mid-cohort.**
