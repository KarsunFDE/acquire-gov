# ADR 0003 — Pilot solicitation-drafting endpoint: streaming + retry

Date: 2026-05-28
Status: Proposed (planning spec — ratified at implementation)
Decision-makers: FDE pair (delivery lead + author)
Phase: 1 — AI Adoption · Milestone M1 (REQ-AID-1, REQ-AID-2, partial REQ-AID-3)
Related: PRD `docs/prd/phase-1-ai-adoption.md` · ADR-0002 (Bedrock anchor) · brownfield Item 4 (locked-failing test)

## Context

The sponsor objective in PRD §1 lands first on M1 — *"draft solicitations in days not weeks."* The current `/draft-solicitation` endpoint in `services/ai-orchestrator/app/main.py` is **deliberately broken** under brownfield Item 4: returns a raw dict, no Pydantic `response_model`, 1-in-3 calls emit `clause_id: null` which trips downstream NullPointerException in the Spring service. Item 4's locked-failing test (`services/ai-orchestrator/tests/test_structured_output_debt.py`) enforces this state until the curriculum modernization week.

The lockfile entry for Item 4 lists `scheduled_unlock_week: W1-Fri`, with `fixed_looks_like: "Pydantic DraftResponse with strict mode; Bedrock raw response parsed + re-emitted."` Today is 2026-05-28 (W1-Thu). Tomorrow afternoon (W1-Fri) is the scheduled unlock window. **The pilot is the Item 4 modernization** — the timing is intentional, not opportunistic.

Pilot intent: prove that a contracting officer can submit a topic + constraints to AWS Bedrock and receive a structured, streamable draft, with a retry policy proven by automated test before any live Bedrock call is made. Nothing is grounded against FAR/DFARS at this stage — RAG and grounding are M2 (ADR forthcoming).

## Decision

### 1. Scope — what ships tomorrow

In:
- `POST /draft-solicitation` — request/response (Item 4 modernized; locked-failing test now passes).
- `POST /draft-solicitation/stream` — NDJSON streaming over `bedrock-runtime:InvokeModelWithResponseStream`.
- Pydantic schemas: `DraftRequest`, `DraftResponse`, `DraftChunk`.
- Retry-with-jitter wrapper around the InvokeModel call, proven by `botocore.stub.Stubber` tests.
- Token-count + tenant-id capture in response (REQ-AID-3 hook; no billing math yet).
- Item 4 lockfile unlock via standard PR process (lockfile flip + `debt-touch-approved` label + template YES branch).

Out (explicit deferrals, each a future ADR):
- Persistence of drafts (Postgres or Mongo) — return-only at pilot.
- CO approval / issuance flow (REQ-AID-4 HITL gate) — defers to ADR-0005.
- Grounding / citations against FAR/DFARS (M2, REQ-RAG-1..4) — defers to ADR-0004.
- Output schema beyond freeform `draft_text` — *which fields a real CO solicitation template needs* is a PRD §11 open question, not closed here.
- Cross-tenant retrieval isolation proof (REQ-RAG-3) — no retrieval yet to isolate.
- Mid-stream retry — see §3.
- Bedrock Provisioned Throughput / quota planning for 10k-user scale — see §6 outstanding.

### 2. Model + region

| Setting | Value | Source |
|---|---|---|
| Provider | AWS Bedrock | ADR-0002 |
| Model ID (live container) | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | compose `environment:` override (operational truth) |
| Model ID (code default) | `anthropic.claude-3-7-sonnet-20250219-v1:0` | `bedrock_client.py`, `.env.example` — brownfield drift, see §6 O2 |
| Region | `us-east-1` | existing pin |
| Auth | `AWS_BEARER_TOKEN_BEDROCK` preferred, IAM access-key fallback, stub if no creds | D-060, `bedrock_client.py` |
| Cost class | Sonnet $3 input / $15 output per 1M tokens | team brief |

The compose `environment.BEDROCK_MODEL_ID` is the **operational source of truth** for the running container; `bedrock_client.py` default and `.env.example` remain `claude-3-7-sonnet-20250219-v1:0` deliberately as curriculum artifacts (§6 O2). The 3.7 model itself reached EOL on Bedrock in 2026-05; the live pilot was bumped to Sonnet 4.5 via the compose override (recorded by ADR-0004 §M10 with US-gov-only deployment scope). Cross-region inference profile (`us.` prefix) is required for Sonnet 4.x on-demand throughput in commercial regions.

The triple-pinned `BEDROCK_MODEL_ID` (`.env.example`, compose, `bedrock_client.py`) is a deliberate brownfield surface — **not consolidated by this ADR.** Cohort consolidates separately.

### 3. Retry policy

Wrapper: `tenacity` (added to `requirements.txt`). Tenacity is preferred over botocore's built-in `retries={'mode': 'standard'}` because tenacity exposes deterministic, injectable sleep — essential for the test guarantee in §4.

| Parameter | Value | Rationale |
|---|---|---|
| `max_attempts` | 4 total (1 initial + 3 retries) | Team brief: max retries = 3 |
| Backoff strategy | Exponential, full jitter | `random.uniform(0, min(cap, base * 2^attempt))` |
| `base` | 1 second | Team brief |
| `cap` | 10 seconds | Bound worst-case latency to ~13s + Bedrock RTT |
| Retry on (botocore exception → HTTP) | `ThrottlingException` (429), `ServiceUnavailableException` (503), `InternalServerException` (500), `ModelTimeoutException` | Team brief: 429 + 5xx. Bedrock-specific transient set per AWS docs |
| **No retry** on | `ValidationException` (400), `AccessDeniedException` (403), `ResourceNotFoundException` (404), `ModelStreamErrorException` (mid-stream) | Non-transient; retry would mask client error or duplicate user-visible chunks |

**Mid-stream errors do not retry.** Once the first chunk has been yielded to the client, a `ModelStreamErrorException` emits a terminal `DraftChunk(event='error')` and closes the connection. Retry from scratch would re-emit the prefix the user already saw and is worse than a clean failure. The retry policy applies only to stream *initiation* — the pre-first-chunk window.

### 4. Test strategy — never hit real Bedrock

`services/ai-orchestrator/tests/test_bedrock_retry.py`. Mock layer: `botocore.stub.Stubber` on the `bedrock-runtime` client. Tests are the green light for the user to load real credentials.

Required assertions:

1. **Transient-then-success.** Stub injects `ThrottlingException` × 1, then a normal `InvokeModel` response. Wrapper succeeds, returns the model body. Sleep was called once.
2. **Transient-then-success at the boundary.** Stub injects 3 transient errors (one 429, one 500, one 503), then a normal response. Wrapper succeeds on the 4th attempt. Sleep called 3 times.
3. **Exhaustion.** Stub injects 4 transient errors. Wrapper raises the final exception. Sleep called 3 times.
4. **Non-retriable fast-fail.** Stub injects one `ValidationException`. Wrapper raises immediately. Sleep was NOT called.
5. **Backoff monotonicity.** Patch `tenacity.nap.time.sleep` with a recorder; assert recorded waits are within the `[0, min(cap, base * 2^attempt)]` envelope for each attempt. Seed `random` for determinism.
6. **Endpoint integration.** `TestClient(app).post("/draft-solicitation", ...)` with Stubber returning a known body → asserts a 200 with a valid `DraftResponse` payload.

The Stubber wires to the exact `botocore` exception classes the production code will raise, so the test proves the retry predicate against the real exception hierarchy — not a hand-rolled stand-in.

### 5. Streaming shape

`POST /draft-solicitation/stream` returns `text/event-stream` (or NDJSON; both acceptable — pick NDJSON for pilot to avoid SSE-on-gateway tuning). Each line is one `DraftChunk` JSON object:

```json
{"event":"delta","request_id":"...","delta":"Section C — Statement of Work..."}
{"event":"delta","request_id":"...","delta":" The contractor shall..."}
{"event":"done","request_id":"...","final":{"request_id":"...","topic":"...","draft_text":"<full concatenated>","model_id":"...","region":"...","tokens_in":42,"tokens_out":318,"stub":false,"generated_at":"2026-05-29T..."}}
```

On error: `{"event":"error","request_id":"...","delta":null,"final":null}` then close.

The sync `/draft-solicitation` endpoint constructs a `DraftResponse` directly — no streaming envelope.

### 6. Outstanding issues (deferred, called out for visibility)

| # | Concern | Why deferred |
|---|---|---|
| O1 | Bedrock quotas at 10k-user scale on a single API key | Pilot is for a CO desk, not 10k users. Provisioned Throughput / cross-region inference profile / per-tenant key rotation is a Phase-1 follow-up ADR once we have real load shape |
| O2 | `BEDROCK_MODEL_ID` drift across 3 files | Brownfield curriculum surface; do not consolidate as a pilot side-effect |
| O3 | Token-count → dollar attribution | Captured but not totaled; REQ-AID-3 bound spending is a budget-guard ADR after the eval gate (ADR-0006) |
| O4 | Correlation-id propagation through the retry/stream path | Item 6 territory; threaded as a TODO comment but not wired (Item 6 is scheduled W5-Tue) |
| O5 | Solicitation template schema | PRD §11 — what fields a real CO solicitation needs is itself a planning question; pilot uses freeform `draft_text` |
| O6 | Streaming through the Spring Cloud Gateway | Gateway may buffer; pilot goes direct to `:8000` from frontend dev. Production gateway wiring is a follow-up |
| O7 | Prompt-injection on `topic` / `constraints` | Item 9 OWASP-LLM01 territory (scheduled W4-Wed); pilot inputs are CO-typed, low-trust-surface |

## Alternatives considered

1. **Net-new `/pilot/draft-solicitation` endpoint** alongside the locked Item-4 endpoint. Rejected: would have left Item 4 unmodernized past its scheduled window, and produced two endpoints with the same purpose. The W1-Fri unlock window makes modernizing in place the cleaner move.
2. **Sync only, defer streaming.** Rejected: streaming is a stated team requirement and is cheap to add when retry policy already lives in a wrapper. Sync endpoint stays as the simpler path; streaming is the second route, not a replacement.
3. **botocore standard retry mode (no tenacity).** Rejected: botocore's standard mode does not let us inject `time.sleep` for tests, does not expose the per-attempt envelope for jitter assertions, and does not allow easy exclusion of `ValidationException`. Tenacity gives us all three.
4. **Mock `invoke_model` directly with `unittest.mock`.** Rejected: tests retry logic at the wrong layer — would pass even if botocore wiring were broken.

## Consequences

- Item 4's locked-failing test flips from failing to passing the moment the response_model + null-clause_id fix lands. `make verify-debt-locks` will fail until the lockfile flip is committed — that is the intended ratchet.
- The `/draft-solicitation` endpoint becomes the first M1 surface the cohort can demo. Downstream Spring code that was guarding against `clause_id: null` no longer needs that guard (separate cleanup, not in this ADR).
- The retry wrapper becomes the pattern reused for `/draft-amendment`, `/answer-qa`, `/eval/ssdd-draft`, `/eval/factor-suggest`, `/agent/intake-triage` in subsequent ADRs. Pilot proves the shape on one endpoint.
- Adding tenacity is the first runtime dependency added in Phase 1; documented in `requirements.txt` with a one-line comment.

## Rollback story

The new streaming route is additive — drop it and the sync endpoint stands alone. The sync endpoint with `response_model=DraftResponse` is the Item 4 modernization itself; rolling back means re-locking Item 4 (flip `locked: false → true`) and reverting the `/draft-solicitation` change. Reversible with one PR.

## Implementation checklist (links to live tasks)

1. Add `tenacity` to `services/ai-orchestrator/requirements.txt`.
2. Wrap `invoke_model` in `bedrock_client.py` with the retry policy from §3.
3. Define `DraftRequest`, `DraftResponse`, `DraftChunk` in `services/ai-orchestrator/app/schemas.py`.
4. Modernize `/draft-solicitation` per Item 4 unlock (response_model + remove null branch).
5. Add `/draft-solicitation/stream` per §5.
6. Write `tests/test_bedrock_retry.py` per §4 — **must pass before the user loads `.env` with the Bedrock bearer token.**
7. Flip Item 4 in `docs/debt-lockfile.yml`; open PR with template YES branch, link this ADR.
