# Hermes Reflex

**Anti-yes-man middleware for Hermes + GBrain.**

Hermes Reflex is a thin skeptical layer that runs before every Hermes response. It checks whether what you're asking for conflicts with your goals, active experiments, known failure patterns, or operating contract — and tells Hermes how to respond accordingly.

Telegram-native. Evidence-backed. Override always available.

---

## The Problem It Solves

Most AI assistants are optimized to say yes. Answer, comply, reduce friction.

That becomes a problem when you're the kind of person who keeps asking for the same productive-seeming thing — rewrite the PRD, add a dashboard, start a new repo — and the assistant just... helps. Politely. Usefully. Into a hole.

```
You:    "Let's add a dashboard to track progress."
Claude: "Great idea! Here's how to set up a React dashboard…"

You:    [three hours later]
        The dashboard has three competing charting libraries.
        The PRD is still not written.
        You have achieved a beautiful graveyard of good intentions.
```

Hermes Reflex doesn't do that. Before Hermes agrees, it checks.

---

## What It Looks Like

### Example 1: Contract Conflict

```
You:    "Maybe we should add a dashboard so I can see patterns visually."

Hermes: "Reflex is blocking this for now.

         Reason: It conflicts with your active No Dashboard Build
         experiment. Your contract says no dashboard before core
         commands work.

         Better move: Ship /patterns first.

         Options:
         1. Build /patterns    ← do this
         2. Park dashboard idea
         3. Override and proceed anyway"
```

### Example 2: Planning Loop Detection

```
You:    "I think we should rewrite the PRD again. It's not quite right."

Hermes: "Reflex is flagging a Planning Loop pattern.

         Evidence:
         - Requested PRD rewrite on May 28
         - Revisited architecture before shipping /experiment create
         - Asked for 'advanced scope' before embedding index was done

         Recommended action: ship one implementation task before
         more planning.

         Options:
         1. Build /experiment create today
         2. Write the PRD revision as a .gbrain note instead
         3. Override"
```

### Example 3: Soft Caution

```
You:    "Maybe later we can visualize these patterns."

Hermes: "Could be useful later — park it for now.
         /patterns and /review are still being stabilized.
         Adding it to your backlog is the right move."
         [mode: NOTE — low confidence, weak evidence, no block needed]
```

---

## How It Works

```
Telegram message
  │
  ▼
┌─────────────────────────────┐
│  Reflex Middleware          │
│                             │
│  1. Command? ───────────►  │  (skip reflex for commands)
│                             │
│  2. Rule engine ─────────►  │  fast keyword/pattern match
│                             │
│  3. Contract check ──────►  │  active goal + constraints
│                             │
│  4. Embedding retrieval ─►  │  GBrain evidence via OpenAI
│                             │
│  5. Cheap LLM critic ─────►  │  JSON decision: mode + reason
│                             │
│  6. Response mode select    │  ALLOW / NOTE / CHALLENGE /
│                             │  CLARIFY / REQUIRE_OVERRIDE /
│                             │  SILENT_LOG
└─────────────────────────────┘
  │
  ▼
Hermes response (with reflex instruction injected)
  │
  ▼
GBrain logs decision, pattern signals, interventions
```

The critic is a cheap JSON-only model. It judges, it doesn't write. The main Hermes model gets a mode instruction and produces the actual response.

---

## Response Modes

| Mode | When it's used |
|---|---|
| `ALLOW` | No risk detected — respond normally |
| `NOTE` | Minor risk, weak evidence — soft caution |
| `CHALLENGE` | Moderate conflict, evidence available — push back |
| `CLARIFY` | Ambiguous intent — ask one question |
| `REQUIRE_OVERRIDE` | Direct contract or experiment violation |
| `SILENT_LOG` | Useful signal, no user-facing pushback needed |

---

## Commands

```
/checkin              — Daily standup (energy, friction, focus, shipped)
/experiment create    — Create a structured experiment
/experiment list      — List active/planned experiments
/experiments          — Alias for /experiment list
/patterns             — View active/watching patterns with evidence
/reflex <question>   — Run the reflex pipeline manually
/review               — Generate weekly review
/override             — Override a challenge and log it
/reflex pause today   — Silence proactive interventions until tomorrow
/reflex pause week   — Silence proactive interventions for a week
/reflex resume       — Resume proactive interventions
```

---

## Real Example: Daily Check-In

```
You: /checkin

Hermes: Energy 1-10?
You: 6

Hermes: Available time today?
You: 90 minutes

Hermes: Biggest friction?
You: I keep wanting to redesign things instead of shipping.

Hermes: Main focus?
You: Hermes Reflex Phase 9.

Hermes: What shipped since last checkin?
You: Finished the critic client with MiniMax fallback.

Hermes: What got avoided?
You: Dashboard idea. Still parked.

─── Check-in saved ───

Reflex recommendation:
Build /patterns next — it completes the evidence loop and
unlocks skillify candidates. Avoid any redesign work today.
```

---

## Real Example: Weekly Review

```
You: /review

Hermes:
Weekly Reflex Review — Week of May 1–7

What shipped:
  • MiniMax critic provider + auto-fallback
  • Rule-mode fallback (no more failing open)
  • HERMES_REFLEX_SKIP_RETRIEVAL env var
  • Weekly Review Generator (Phase 9)
  • Skillify Candidates (Phase 10)
  • 4 new integration tests

What stalled:
  • /patterns confidence scoring (deprioritized)

Patterns fired:
  • Planning Loop: 2 times
  • UI Avoidance: 1 time (dashboard idea, parked)

Overrides: 0

Experiment status:
  No Dashboard Build — active. 3/4 commands shipped.

Next week recommendation:
  Ship /patterns before any new feature work.

Stop doing:
  Rewriting README before verifying tests pass.
```

---

## Architecture

```
src/
  core/          — middleware, rule_engine, operating_contract,
                   response_modes, schemas, pause
  gbrain/        — storage, paths, frontmatter, markdown I/O
  embeddings/    — OpenAI client, chunker, SQLite indexer, search
  critic/        — prompt, client (OpenAI + MiniMax), parser, decision
  patterns/      — rules, detector, lifecycle, evidence
  commands/      — checkin, experiment, patterns, reflex,
                   review, override, pause
  reviews/       — weekly review generator
  interventions/ — skillify candidate detection
  experiments/   — experiment CRUD
tests/           — 398 unit + integration tests
```

---

## Running It

```bash
git clone https://github.com/sprajapati024/Hermes-Reflex
cd Hermes-Reflex

pip install -r requirements.txt

# Required
export OPENAI_API_KEY="sk-..."

# Optional — MiniMax fallback if no OpenAI key
export MINIMAX_API_KEY="..."

# GBrain storage root
export HERMES_REFLEX_GBRAIN_ROOT="~/gbrain"

# Run tests
PYTHONPATH=src python3 -m pytest tests/ -v
```

---

## Phase Status

All 10 phases complete and on `main`.

| Phase | Description | Commit |
|---|---|---|
| 0 | Project bootstrapping | `80f08a1` |
| 1 | GBrain storage layer | `c918fbf` |
| 2 | Operating contract | `355bc07` |
| 3 | Embedding + retrieval | `dbb500d` |
| 4 | Rule engine (7 risk types) | `7cc5fe5` |
| 5 | Cheap critic layer | `c03bd90` |
| 6 | Reflex middleware | `6f9a3a9` |
| 7 | Telegram commands | `2f0034c` |
| 8 | Pattern lifecycle | `c2c415e` |
| 9 | Weekly review generator | `02983ae` |
| 10 | Skillify candidates | `02983ae` |

**Latest:** `b7bf834` — merged PR #4 (verbose pipeline mode, per-chat `/reflex verbose`, `/experiments` alias, cache leakage hardening)

---

## First Experiment: No Dashboard Build

The operating contract that Hermes Reflex enforces on itself:

```
Hypothesis: If you avoid frontend/dashboard work for 7 days,
you ship the Hermes Reflex core loop faster.

Rules:
  • No dashboard
  • No frontend
  • Telegram commands only
  • GBrain markdown only

Metric: working Telegram commands shipped
Success criteria: 4 commands in 7 days
```

This experiment is how the system proves the anti-yes-man loop works before adding any surface area that would make it irrelevant.

---

## Docs

- [PRD.md](./PRD.md) — Product requirements and theory
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) — Phase-by-phase build guide
- [USER_STORIES.md](./USER_STORIES.md) — User flows and experience
- [QA_AUDIT.md](./QA_AUDIT.md) — Theory audit and loophole fixes
- [AGENTS.md](./AGENTS.md) — Agent build instructions
