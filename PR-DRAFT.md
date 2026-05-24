# PR Draft — Agent A: Backend depth expansion for acquire-gov

**Branch:** `feature/agent-A-backend-depth`
**Base:** `main` @ `472a96e` (`v0.1-legacy-baseline`)
**Status:** DO NOT PUSH — orchestrator authorizes manually.

## Title

`feat(acquire-gov): backend depth expansion — 50 endpoints across 3 Java services + ai-orchestrator Bedrock`

## Debt-touch checkbox

- [x] **NO** — this PR preserves all 12 brownfield-debt items intact.
      Verified via `bash .github/scripts/run-locked-tests.sh
      docs/debt-lockfile.yml`: 7 authored locked-failing tests still fail
      (Items 4, 5, 7, 9, 10, 11, 12); 5 items pending test-author
      (iter-12 — not in scope here); zero items flipped to "now passing".

## Summary

Builds out `acquire-gov` from the W1-Tue-survivable baseline (the
`SolicitationController` + 1 stub endpoint shape it shipped with) to the
**CAMEO/COMET-shaped federal-acquisitions surface** described in
`fde-10-week/training-project/feature-inventory-target.md`:

- **50 endpoints** across api-gateway, solicitation-service,
  evaluation-service, ai-orchestrator (matches the inventory's 8 + 17 + 17 +
  8 split).
- **18 entities** (7 in solicitation-service, 10 in evaluation-service +
  expanded AuditEvent shape) — modeled per FAR Parts 5, 15, 42 and CPARS /
  FPDS / SAM.gov shapes.
- **6 multi-step workflows** wired end-to-end (drafting → publication; Q&A
  + amendments; sealed proposal intake + unseal; eval → consensus → SSDD →
  award; contract admin + modifications; CPAR + 60-day rebuttal).
- **5 reports** (`/api/reports/acquisition-pipeline`,
  `/vendor-past-performance`, `/contract-spend`, `/oig-findings-status`,
  `/audit-log-activity`).
- **5 notification surfaces** (no-op `Notifier` component).
- **4 admin views backends** (`/admin/users`, `/admin/audit`,
  `/admin/config`, `/admin/findings`).
- **8 ai-orchestrator endpoints** with **real AWS Bedrock InvokeModel
  wiring** per D-060 (boto3 `bedrock-runtime`, falls back to stub when AWS
  creds unresolvable; NO managed services — D-050 boundary preserved).

## Stack constraints honored (D-056)

- Spring Boot 2.7.18 + Java 11 + `javax.*` + Spring Security 5 +
  AWS SDK for Java v1 across all 3 Java services.
- `WebSecurityConfigurerAdapter` pattern preserved in solicitation-service.
- `RestTemplate` for inter-service calls (no WebClient, no Spring AI, no
  framework-modern OTel/Micrometer auto-config).
- Spring Data MongoDB `@Document` idiom; evaluation-service gains MongoDB
  dependency to match solicitation-service (era-authentic — same SB 2.7
  starter line).

## Brownfield-debt items preserved (verified)

| # | Item | Surface preserved |
|---|------|-------------------|
| 1 | JWT signature-skip on `/api/public/*` | `PublicOpportunitiesController` now populates the public surface; `JwtSignatureSkipFilter` untouched. |
| 2 | Audit-log race | Every workflow state transition (publish, cancel, amend, qna submit/answer, proposal submit/ack, eval create/score/SSDD, award, debrief req, contract create/mod/QASP, CPAR open/rebuttal/finalize, finding open, vendor/user provisioning) routes through `AuditLogger.recordAsync` / `EvalAuditLogger.recordAsync`. |
| 3 | No circuit breaker eval→sol | `SolicitationClient` untouched; `EvaluationService.submitScore` + `ReportsController.auditLogActivity` + `ContractService.listDeliverables` add new caller paths that exercise the same no-breaker hop under TEP-week load. |
| 4 | No structured output validation | 5 distinct AI endpoints (`/draft-solicitation`, `/draft-amendment`, `/answer-qa`, `/eval/ssdd-draft`, `/eval/factor-suggest`, `/agent/intake-triage`, `/rag/clause-search`) all return `dict[str, Any]` — no `response_model`. `/draft-solicitation` 1-in-3 null `clause_id` drift unchanged. |
| 5 | Pre-v1.0 LangChain patterns | `legacy_chain.py` untouched; `main.py` imports it (kept reachable); 3 entry points named per inventory (Drafting Wizard, Amendment Editor, Notifier.cparWindowOpened-via-/draft-amendment). |
| 6 | Inconsistent correlation-IDs | All 4 services keep distinct keys: api-gateway = `X-Request-ID`, solicitation-service = `correlationId`, evaluation-service = `traceId`, ai-orchestrator = none. New endpoints do not thread a correlation-id. |
| 7 | `pinecone-client` listed but unused | `requirements.txt` line untouched; no `import pinecone` anywhere; `AdminConfigController` *advertises* both pinecone + atlas as "available vector stores" (the lie the cohort discovers via grep). |
| 8 | Frontend hardcodes service URL | Untouched — frontend not in scope (Agent B). |
| 9 | No OWASP input sanitization | 4 user-input surfaces named in inventory all accept raw HTML: `SolicitationCreateRequest.description`, `QnaRequest.question` + `QnaAnswerRequest.answer`, `DebriefRequest.narrative`, `Cpar.vendorRebuttal`. Plus the new `Amendment.changeSummary` + `Solicitation.sections` map values. |
| 10 | No multi-tenant boundary | Every new repository has both `findAll()` callers (the leak path) AND `findByAgencyId(...)` declarations (the W2-Wed fix surface, unwired). `PublicOpportunitiesController.list`, `VendorService.listAll`, `UserService.listAll`, all `ReportsController` aggregations, all `*Service.listForSolicitation` / `listForContract` / `listForVendor` reproduce the pattern. |
| 11 | Dockerfiles `:latest` | All 4 Dockerfiles unchanged; `AdminConfigController` exposes the image-pin status (`ai-orchestrator` hand-pinned, other 4 on `:latest`) as visible surface. |
| 12 | GHA lint disabled | `infra/github-actions/ci.yml` untouched; `FindingController` provides the meta-mirror surface (cohort can open a Finding against the repo's own CI). |

## Local build/verify

| Service | Command | Result |
|---------|---------|--------|
| solicitation-service | `mvn -B verify` | **PASS** (10s, JDK 11.0.21 Corretto) |
| evaluation-service | `mvn -B verify` | **PASS** (1s) |
| api-gateway | `mvn -B verify` | **PASS** (6s) |
| ai-orchestrator | `pytest -m "not brownfield_debt"` | 5 tests all debt-marked → all deselected → green |
| `bash .github/scripts/run-locked-tests.sh docs/debt-lockfile.yml` | — | **OK: all locked items still locked** (7 failing-by-design + 5 pending test-author). |

No remote CI yet (per HITL #6 — orchestrator decides when to push).

## Notes for reviewers

- D-060 Bedrock authorization: real `boto3.client("bedrock-runtime")` calls
  run when AWS credentials resolve; stub fallback otherwise. Tested with
  ResourceNotFoundException-on-EOL-model path → graceful stub fallback.
- The 1-in-3 null-clause_id drift on `/draft-solicitation` (Item 4) now
  *also* calls Bedrock, but the null-clause_id surface is preserved as the
  *response shape* not the *Bedrock body*. Lock test still fails.
- evaluation-service got a new `spring-boot-starter-data-mongodb` dep — era-
  authentic addition for the 10 new entities; no `jakarta.*`, no Boot 3.
- Two warnings I left intentional: `SecurityConfig` deprecation warning
  (the SB 2.7 + Security 5 + `WebSecurityConfigurerAdapter` pattern is the
  W4 modernization target per D-056); duplicate-naming caution on
  `MultiTenantBoundaryDebtTest` will surface when `findByAgencyId` actually
  gets wired (W2-Wed).
