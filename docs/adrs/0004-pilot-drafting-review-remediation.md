# ADR 0004 — Pilot drafting endpoint: review-remediation plan

Date: 2026-05-29
Status: Proposed (planning — fixes land before lockfile flip)
Decision-makers: FDE pair (delivery lead + author)
Phase: 1 — AI Adoption · Milestone M1
Related: ADR-0003 (pilot spec) · PRD §6 REQ-AID-1..4 · PRD §7 principles

## Context

The ADR-0003 pilot landed live Bedrock for the first time (Sonnet 4.5 cross-region inference profile) and proved out the request/response endpoint at the smoke-test bar. A senior-engineer review found two **Blocker**-class and nine **Major**-class issues plus a pile of Minors. Findings accepted in full. This ADR records the remediation plan, splits work into "must fix before lockfile flip + PR merge" vs "follow-up ADR," and writes down the test additions the next round needs.

The reviewer's full critique is referenced as input but not duplicated here — this ADR captures only **decisions** and **scope**.

**Out-of-scope from the review:** Finding M10 (cross-region inference profile binding `us.anthropic.claude-sonnet-4-5-...` to US regions) is **not in scope for remediation.** This is a US-federal-government engagement; non-US developer regions are not a supported deployment target for the pilot. The compose comment is updated to state this explicitly so a future cohort working on a non-gov fork knows where the boundary lives.

## Decisions

### Severity triage

| ID | Severity | Title | Decision |
|---|---|---|---|
| B1 | Blocker | `wait_exponential_jitter` is bounded jitter, not full jitter | **Fix in PR** — swap to true full jitter |
| M1 | Major | Exhausted retries swallowed into `stub: true` fallback | **Fix in PR** — raise instead, FastAPI surfaces 502 |
| M2 | Major | `_is_retriable` over-retries broad `BotoCoreError` family | **Fix in PR** — narrow to explicit tuple |
| M3 | Major | `Retrying(...).reraise=True` masking via tenacity drift | **Fix in PR** — add `RetryError` to catch tuple |
| M4 | Major | Mid-stream Bedrock error frames silently dropped | **Fix in PR** — handle inline error event keys |
| M5 | Major | `draft_text="[empty]"` placeholder on empty output | **Fix in PR** — emit error, not synthetic text |
| M6 | Major | Required `tenant_id` 422s Item 4 locked test (fake-green) | **Fix in PR** — see §M6 below |
| M7 | Major | Backoff-envelope test too loose to detect B1 | **Fix in PR** — tighten upper bound + add lower bound |
| M8 | Major | No coverage for `BotoCoreError` non-`ClientError` branch | **Fix in PR** — `monkeypatch`-raise tests |
| M9 | Major | `tenant_id` is caller-asserted, unenforced | **Fix in PR** — rename + docstring + TODO citing REQ-RAG-3 |
| M10 | Major | `us.` inference profile region binding | **OUT OF SCOPE** — US-gov-only deployment |
| M11 | Major | No cost guardrail / per-tenant token cap | **Follow-up ADR-0006** — pilot ships with capture-only |
| N1–N10 / T1–T6 | Minor / Nit | Various | **Mixed** — see §Minor sweep |

### B1 — True full jitter

Replace `wait_exponential_jitter(initial=1, max=10)` with a custom `wait_base` subclass implementing full jitter:

```
wait = random.uniform(0, min(cap, base * 2 ** (attempt - 1)))
```

`base = RETRY_BASE_SECONDS` (1.0), `cap = RETRY_CAP_SECONDS` (10.0). Document the formula inline next to the class.

Why not amend ADR-0003 to bounded jitter instead: pilot scales toward a CO desk today, but ADR-0003 §6 O1 explicitly anticipates 10k-user follow-on work where thundering-herd avoidance matters. Locking in the correct primitive now is cheaper than refactoring under load later.

### M1 — Stop swallowing exhausted retries

Distinguish two failure modes inside `invoke_model` / `invoke_model_stream`:

- **No client at all** (`_get_client()` returns None, no boto3 or no credentials). Return stub with `stub: true`. Preserves first-day learner path.
- **Client exists, retries exhausted or non-retriable raised.** Raise the underlying exception. The FastAPI endpoint translates to:
  - `503 bedrock_unavailable` for transient-exhausted (Throttling / ServiceUnavailable / InternalServer / ModelTimeout)
  - `502 bedrock_request_invalid` for non-retriable (Validation / AccessDenied / ResourceNotFound)
  - `500 bedrock_unknown_error` for anything else (defensive)

Streaming variant emits one terminal `DraftChunk(event="error", error_code=..., error_message=...)` and closes — consistent with the sync 5xx in shape (the client gets an error frame either way).

Add a FastAPI exception handler that maps these to the right HTTP code and writes an audit log entry (Item 6 is preserved debt — log without correlation-id for now; the eventual W5-Tue fix wires correlation through).

### M2 — Narrow `_is_retriable`

Replace the broad `BotoCoreError-except-NoCredentialsError` branch with an explicit allow-list:

```
TRANSIENT_BOTOCORE_EXC = (
    ReadTimeoutError, ConnectTimeoutError, EndpointConnectionError,
)
```

`ParamValidationError`, `SSLError`, `MD5UnavailableError`, `HTTPClientError`, `IncompleteReadError`, `ProxyConnectionError` → fall through to `False`. Add a regression test for `ParamValidationError` proving zero retries.

### M3 — `RetryError` defense in depth

Add `from tenacity import RetryError` and include it in the `except (...)` tuple in both `invoke_model` and `invoke_model_stream`. Keep `tenacity==9.0.0` pin tight (already in `requirements.txt`).

### M4 — Inline mid-stream error event handling

Bedrock's `InvokeModelWithResponseStream` delivers errors as event-stream frames alongside `chunk`. Iterate looking for these keys before processing `chunk`:

- `internalServerException`
- `modelStreamErrorException`
- `throttlingException`
- `validationException`
- `modelTimeoutException`

Yield `{"type": "error", "code": <key>, "message": <inner.message>, "request_id": rid}` and terminate the generator. Confirm by adding a unit test that injects a synthetic event-stream containing one of these keys mid-iteration.

Retry policy still does not re-attempt mid-stream (ADR-0003 §3 invariant). The fix is about *surfacing* the error, not retrying it.

### M5 — No synthetic "[empty]" payload

Drop the `or "[empty]"` substitution. If the model emits no content:
- Sync path: raise — translates to 502 per M1's handler.
- Stream path: yield `{"event": "error", "error_code": "empty_response"}` and close — no terminal `done`.

Update `DraftResponse.draft_text` Field constraint to remain `min_length=1` so any code attempting to fabricate empty text fails fast at construction.

### M6 — Fix the fake-green on Item 4 locked test

Two options surfaced; **decision: option (a)** — keep `tenant_id` required and **update the locked test in the same PR**. Rationale:

- The locked test's purpose is "endpoint produces a valid `DraftResponse` over 60 calls with no null `clause_id`." 422-via-missing-`tenant_id` makes the assertion vacuously true. That's the failure mode the reviewer caught.
- The lockfile-flip PR already legitimately touches Item 4. Updating its locked test inside that PR is the right shape — the test must reflect *post-modernization* truth, not pre.
- Option (b) (make `tenant_id` optional with a sentinel) bakes in audit-log dilution from day one and creates a "now you must include tenant_id, but here's a default that lies" wart.

Update `tests/test_structured_output_debt.py` POST body to include `"tenant_id": "agency-debt-test"`. Note the touch in the PR description (this is a locked test, but its assertion is preserved — only the request body is amended). Confirm with curriculum owner before merge.

### M7 + M8 — Tighten + extend retry tests

**M7 fix.** In `test_backoff_waits_bounded_by_envelope`:
- Drop the `+ base` slack term.
- Upper bound becomes exactly `min(cap, base * 2 ** (attempt - 1))` (matches the new full-jitter formula).
- Add a *lower-bound* assertion: across N=200 simulated runs with a seeded RNG, assert `min(observed waits at attempt k) < 0.1 * envelope_k` — a bounded-jitter implementation cannot satisfy this, so the test fails loudly if someone regresses to bounded jitter.
- Seed `random.seed(...)` in fixture to make the distribution check deterministic.

**M8 fix.** Add two tests using `monkeypatch.setattr(client, "invoke_model", lambda **_: (_ for _ in ()).throw(...))`:
- `test_endpoint_connection_error_retries` — assert 3 retries fired.
- `test_param_validation_error_does_not_retry` — assert 0 retries; assert 502 surfaces (per M1's handler).

### M9 — Honest naming + comments for `tenant_id`

`DraftRequest.tenant_id` stays as the field name (downstream cost-attribution tooling will key on it). But:
- Add Field `description="Caller-asserted tenant identifier. NOT verified against JWT in pilot. PRD §6 REQ-RAG-3 will enforce. Trust at audit-log level only."`
- Add a module-level comment in `schemas.py` summarizing the pilot's "audit-only, unenforced" stance on tenant_id + feature_id.
- Add a TODO with the literal string `REQ-RAG-3-enforcement` so the M2-milestone planning grep finds it.

### M10 — Out of scope (US-gov deployment)

Update the `infra/docker/docker-compose.yml` comment block at the `BEDROCK_MODEL_ID` line to state:

> "Cross-region inference profile binds to US regions. Deployment is US-federal-government only; non-US regions are not a supported target. Forks operating outside US-gov must replace this with a region-appropriate model ID before bringing up the stack."

No code change.

### M11 — Cost guardrail deferred to ADR-0006

The reviewer's "10 lines of in-process counter" is a fair short-term suggestion but it would be the first piece of governance scaffolding that survives past the pilot — premature without ADR coverage. Pilot ships with token-count *capture* only (already implemented). ADR-0006 (forthcoming) defines the per-tenant/per-feature cap shape, breach policy, and where the counters live (in-process for pilot, externalized later).

Until ADR-0006 lands, the bearer token's blast radius is the bearer token's quota itself — Bedrock's account-level limits act as a hard ceiling. Document this trade explicitly in ADR-0003's §6 O3 update (below).

### ADR-0003 reconciliation

Two drifts the reviewer flagged that are not code fixes:

- **§2 model row** says `claude-3-7-sonnet`; compose says `claude-sonnet-4-5`. Update §2 to: "Pinned at `us.anthropic.claude-sonnet-4-5-20250929-v1:0` via the compose `environment:` override (the running container's source of truth). `bedrock_client.py` default and `.env.example` remain `claude-3-7-sonnet-20250219-v1:0` per §6 O2 brownfield drift — those are deliberate teaching artifacts and are not consolidated by this ADR. The compose override is the operational truth for the live pilot."
- **§5 streaming envelope example** in the ADR shows `delta:null, final:null` for the error frame; the code emits the envelope without those fields. Update the ADR example to match the code (use `error_code` + `error_message`; omit `delta` / `final`).

### Minor sweep

| ID | Decision |
|---|---|
| N1 | Add comment in `schemas.py` predicting gateway-`extra` collision. |
| N2 | Generate the `request_id` in the stream route up front (`uuid.uuid4()`), pass into `invoke_model_stream(request_id=...)`. Removes the "DRAFT-unknown" reachability. |
| N3 | Add inline comment that `default_factory=lambda` is intentional vs import-time freeze. |
| N4 | Keep `protected_namespaces=()` with its existing comment. No action. |
| N5 | Already pinned `tenacity==9.0.0`. No action. |
| N6 | Add one test that asserts the full request body shape (`anthropic_version`, `max_tokens`, `messages`, `system`). |
| N7 | In `_generate()`, propagate stub-ness onto every `delta` envelope so a mid-stream consumer can detect stub before `done`. New `DraftChunk` field: `stub: bool = False`. |
| N8 | Untouched preserved debt; no action. |
| N9 | Remove the dead `_BOTO_AVAILABLE` check inside `_is_retriable`. |
| N10 | No action. |
| T1 | ADR §5 example fix (see ADR-0003 reconciliation above). |
| T2 | Note in next ADR; no action this PR. |
| T3 | No action. |
| T4 | Add `⚠ Item 9-adjacent` banner to `/draft-solicitation` + `/draft-solicitation/stream` docstrings. |
| T5 | Add positive `clause_id` shape assertion (`re.match(r"^DRAFT-[0-9a-f]{8}$", ...)`) in retry tests. |
| T6 | Re-run smoke test post-merge; update report. |

## Merge gate (replaces ADR-0003 task #8 single step)

Before flipping `docs/debt-lockfile.yml` Item 4 `locked: true → false` and opening the PR with `debt-touch-approved`:

1. B1 fix lands + new full-jitter formula tested (M7).
2. M1 fix lands + endpoint surfaces 5xx instead of stub on exhaustion + audit log entry written.
3. M2 narrow retry list + M8 coverage for `ParamValidationError` and `EndpointConnectionError`.
4. M3 `RetryError` in except tuples.
5. M4 mid-stream error frame handling + unit test injecting `internalServerException`.
6. M5 empty-response error path (sync + stream).
7. M6 locked-test body updated to include `tenant_id`. Curriculum-owner sign-off recorded in PR.
8. M9 schema field description + TODO.
9. M10 compose comment updated to state US-gov-only deployment scope.
10. ADR-0003 §2 + §5 reconciliation edits.
11. Re-run full ai-orchestrator pytest suite — green except the still-locked Items 5 + 7.
12. Re-run live smoke test against Sonnet 4.5; verify `stub: false`, real token counts, structured draft.

Only after all 12 are green does the lockfile flip + PR open.

## Out of scope (explicitly deferred to follow-up ADRs)

- **ADR-0005** — CO approval / issuance HITL gate (REQ-AID-4).
- **ADR-0006** — Token budget guardrail + per-tenant/feature caps (M11).
- **ADR-0007** — Real tenant boundary enforcement from JWT (REQ-RAG-3, addresses M9 enforcement gap).
- **ADR-0008** — Correlation-ID + audit-log threading (Item 6 territory; W5-Tue curriculum unlock).
- **ADR-0009** — Grounded retrieval + citations (M2 milestone, REQ-RAG-1..4).

## Consequences

- The fix work is larger than the original pilot landed. Tomorrow afternoon's "first hit" demo already happened (Sonnet 4.5, real draft, real tokens). The remediation PR is the *production-grade* version of the same surface.
- The reviewer's findings reframe what "pilot done" means: not "first live call works," but "first live call works AND the failure modes are honest, observable, and gated." That distinction is the actual REQ-AID-2 requirement ("AI output is safe to consume — no malformed or ungrounded content silently passes downstream").
- The deferred items (M11 + REQ-AID-4 + REQ-RAG-3 enforcement + Item 6 correlation) accumulate into the M2 planning agenda. Carry them forward as a single discussion topic in the next planning session.

## Rollback story

The remediation is additive on top of ADR-0003. Rolling back means reverting the remediation PR; ADR-0003's surface remains the pilot baseline. The lockfile flip is the final step — if any of items 1–12 above is incomplete, the lockfile stays at `locked: true` and main remains green via the debt-enforcement invariant.
