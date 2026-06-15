# DEMO-REDESIGN — generate-and-review solicitation drafting

**Written:** 2026-06-15 · **Branch:** `cj/m1-langchain-integration` · **Mode:**
overnight autonomous build + stub-verify (live smoke deferred to fresh Bedrock
key in the AM). · **Predecessor:** `DEMO-HANDOFF.md` (demo blockers, current
state). Read that first.

## Build status — 2026-06-15 overnight (UNCOMMITTED)

| Phase | Status | Notes |
|---|---|---|
| 1 Cost safety | ✅ done | all 3 Sonnet drafters bounded (`DRAFTER_RECURSION_LIMIT=12`); `max_tokens`+`max_retries` centralized in `model_factory.py`; loop-cap regression test (`tests/agents/test_recursion_guard.py`) |
| 2 Boilerplate D-G + K | ✅ done | `app/agents/boilerplate.py` — D-G one Haiku call, K programmatic set-aside→clause; FinalDraftSection-shaped |
| 3 Coordinator wiring | ✅ done | `generate_boilerplate` node + merge into Part I/IV at aggregate |
| 4 Editable review | ✅ done | Step 12 renders all A–M editable w/ provenance badges |
| 5 Form fields | ✅ done | PoP, place, eval-approach, key-personnel — schema + state + frontend + payload |
| 6 Few-shot/token records | ✅ done | `docs/reference/solicitation-fewshot.md` (cited) |
| Stub mode | ✅ done | `AI_STUB_MODE` (compose=`true`) — full HTTP path returns all 12 sections w/ **no Bedrock, no Mongo** (verified via TestClient) |
| 7 Demo script | ✅ done | `DEMO-SCRIPT.md` |
| 6 Diagrams | ⏳ in progress | background agent updating `docs/diagrams/ai-architecture.md` |
| 3 **C-first live sequencing** | ⏸ **DEFERRED** | live-path only (invisible in stub demo); riskiest change to the working HITL/batch path; critic already flags C↔L/M misalignment warn-only. See note below. |

**Verification:** backend `pytest tests/` → 460 passed, 2 skipped, only the 3
locked brownfield-debt failures (expected). Frontend: build OK (503 kB, 3 kB over
warn budget), 15 specs pass.

**Deferred — C-first sequencing rationale:** the coordinator fans out Part I
{C,H} ∥ Part IV {L,M} in one superstep via `Send`. Sequencing C→L/M means
restructuring that fan-out and threading drafted-C text into the Part IV
payload, which touches the replay-safe interrupt/resume handshake (phase-2 HITL
tests). Doing that under context pressure the night before a demo is the wrong
risk for a **live-only** quality gain that the warn-only critic already
mitigates and that the stub demo never exercises. Pick it up first in the AM
with the HITL tests in front of you.

## 0. The goal (one sentence)

Turn the wizard from "fill 8 sections by hand, AI drafts 4" into
**"AI drafts everything it safely can; the human reviews and edits"** — minimize
keystrokes, maximize coverage, prove the architecture, and do it **without ever
risking a token-runaway loop**.

Demo win condition: a CO opens the wizard, fills Step 1, clicks **one** button,
and lands on a Review step where **every** section A–M is populated and editable,
with provenance and a consistency check — all reproducible against stubbed
Bedrock returns (so it works tonight, before the key lands).

## 1. Non-negotiable constraint — NO token-runaway loop

The 2026-06-12 critic incident (one run = 2.8M tokens) must never recur. The
critic got capped afterward; **the expensive Sonnet drafters were never bounded**
and currently run at langgraph's bound default `recursion_limit: 9999`
(langchain 1.3.8 / langgraph #7313). That is the live risk.

| Invoke site | Model | Today | Must be |
|---|---|---|---|
| `api/draft.py:144` section drafter | Sonnet | none → 9999 | bounded |
| `api/resume.py:116` resume | Sonnet | none → 9999 | bounded |
| `nodes.py:165/174/179` part drafter | Sonnet | none → 9999 | bounded |
| `api/critic.py` + `nodes.py:358` critic | Nova | 3 ✅ | unchanged |
| NEW D-G/K boilerplate gen | Haiku | — | **no agent loop at all** |

Hard rules for this build:
- Every `create_agent` invoke passes an explicit `recursion_limit`
  (`DRAFTER_RECURSION_LIMIT`, default ~12 — enough for retrieve→extract→gate→
  draft→validate→final, tight enough to kill a loop fast).
- Every `ChatBedrockConverse` gets a `max_tokens` cap (per-section table, §5) and
  low `max_retries` (boto3 retry-storm guard).
- New boilerplate generators (D-G, K) are a **single `with_structured_output()`
  call — no agent, no tools, no loop surface**. Structurally cannot recurse.
- **Regression test:** a mock agent that always re-emits a tool call must die at
  the cap with a bounded call count, asserted in CI. This is the guard that
  would have caught the original incident.

## 2. Section generation plan (DECIDED — scope: D-G + K only)

Only C, H, L, M generate today (Sonnet agents). New coverage:

| Sec | Today | Target | Mechanism |
|---|---|---|---|
| A Form | human | human | unchanged (cover sheet, signatures) |
| B Prices/CLINs | human | human | unchanged (pricing = CO judgment) |
| C SOW | Sonnet agent | Sonnet agent | **drafted FIRST (root)** |
| D Packaging | human | **generated** | Haiku, single bundled call w/ E,F,G |
| E Inspection | human | **generated** | ″ |
| F Deliveries | human | **generated** | ″ |
| G Admin Data | human | **generated** | ″ |
| H Special | Sonnet agent | Sonnet agent | sequenced after C |
| I Clauses | programmatic | programmatic | unchanged (clause matrix) |
| J Attach | human | human | unchanged |
| K Reps/Certs | human | **generated** | Haiku single call, set-aside-driven |
| L Instr | Sonnet agent | Sonnet agent | **sequenced after C** |
| M Eval | Sonnet agent | Sonnet agent | **sequenced after C** |

Result: of 12 sections, **9 auto-populate** (C,D,E,F,G,H,I,K,L,M); only A, B, J
need human entry. One "Draft AI Parts" click fills them all.

## 3. C-first sequencing (DECIDED)

Today: batch fans out Part I {C,H} ∥ Part IV {L,M} as parallel siblings → L/M are
drafted blind to the SOW (roadmap §5.1 gap). FAR requires L/M written against C.

Target DAG (behind the scenes — user sees one button):
```
plan → draft C  ──┬─► draft H   (context: C) ┐
                  ├─► draft L,M (context: C) ├─► resolve I (programmatic) ─► aggregate ─► critic ─► END
                  └─► gen D-G,K (context: C) ┘   pass-through J
```
C is the root; H/L/M/D-G/K all receive drafted C as context. I (clauses) and J
(attachments) stay independent. Keeps the `MAX_BATCH_FAN_OUT` cap intact.

## 4. New Step-1 form fields (DECIDED — all four)

Add to the wizard Step 1 form + `BatchDraftRequest`/`DraftSectionRequest` context,
threaded into draft prompts:

| Field | Drives |
|---|---|
| Period of Performance (base + option years) | F (delivery), C scope framing |
| Place of Performance (on-site/remote/hybrid + location) | C, H (clearance/security) |
| Eval approach (LPTA vs best-value tradeoff) | **L + M structure (high payoff)** |
| Key personnel required (y/n + roles) | H, L (staffing instructions) |

All optional/soft-required (preflight degrades gracefully, ADR-0015 pattern — do
not make them hard-block).

## 5. Token caps + few-shot (G5 — research running)

Research **DONE** (2026-06-15, cited) → records file
`docs/reference/solicitation-fewshot.md`. Per-section `max_tokens` (from real
SAM.gov/GSA norms, kept tight):

| Sec | max_tokens |
|---|---|
| C | 6000 (chunk if long) |
| L | 4000 |
| M | 2500 |
| H | 1800 |
| K | 600 |
| D | 300 · E 350 · F 450 · G 450 |

Few-shot: short priming snippets per generated section live in the records file,
injected into the relevant prompt. Two research findings that change the design:
- **D/E/F/G are near-verbatim FAR/GSAR clause text** — prefer retrieving canonical
  clause text + light merge over free-gen; few-shot anchors provided.
- **K = incorporation-by-reference** (52.204-8 + ONE set-aside notice clause),
  not free-drafted certs. **Reuse the Part II clause-matrix set-aside→clause
  pattern**; always pair 52.219-14 with any small-business set-aside.

## 6. Full editable review (G3)

Step 12 today shows section *lengths* in a table + the critic. Target: render
**every** section A–M in an editable textarea on the review step, each with
provenance badge (human / ai / ai-edited) and the existing per-section "fix"
links. Generate-and-review means the review step IS the main editing surface.

## 7. Deliverables for the AM (cowork slide deck)

- Regenerated arch diagrams (`docs/diagrams/ai-architecture.md`) reflecting the
  new DAG (C-first sequencing, Haiku boilerplate path, model tiering
  Sonnet/Haiku/Nova) — G6.
- **Demo input script** (`docs/specs/m1-agentic-drafting/DEMO-SCRIPT.md`) — G7:
  realistic Step-1 values + constraint text + refinement/regenerate prompts a
  presenter copy-pastes. Distinct from stub returns so codebase-readers don't
  dismiss it as "all stubbed."

## 8. Execution phases (overnight)

1. **Cost safety** — `DRAFTER_RECURSION_LIMIT` + `max_tokens` + low `max_retries`
   at all drafter sites; loop-cap regression test. (CRITICAL — gates everything.)
2. **Boilerplate gen** — D-G + K single-call Haiku generators (bounded, stubbable).
3. **C→others sequencing** in coordinator DAG.
4. **Editable review step** (every section A–M).
5. **Form fields** (4) + thread into draft context.
6. **Few-shot/token records** from research output.
7. **Diagrams regen + demo script.**
8. **Stub-mode end-to-end verify** (no key needed); live smoke when key lands.

Each phase independently committable. Stub fallback must work at every phase so
the demo path is green before the Bedrock key arrives.

## 9. Out of scope (do NOT pre-do — Phase 2 / M3 territory)

Per CLAUDE.md + PRD §4: no framework/runtime hops, no real auth on `/api/ai/**`
(stays demo-permitAll), no Section J file storage, no critic hard-fail surface,
no OTel/circuit-breaker/resilience tooling. Boilerplate gen is additive M1
adoption, not modernization of inherited debt.
