# Hermes Reflex

**Anti-yes-man reflex middleware for Hermes + GBrain.**

Hermes Reflex prevents LLMs from blindly agreeing with requests that conflict with your goals, active experiments, known patterns, or operating contract. Telegram-native. Evidence-backed. Override always available.

---

## What It Does

```
You: "Let's add a dashboard to track progress."
Hermes: "Reflex is flagging a contract conflict."
        "Active experiment: No Dashboard Build."
        "Recommended action: ship /patterns first."
        "Override or park it — your call."
```

Hermes Reflex adds a skeptical decision layer before Hermes responds:

```
Telegram → Reflex Middleware
  → Rule engine (fast, no LLM)
  → Operating contract check
  → OpenAI embedding retrieval
  → Cheap LLM critic (JSON only)
  → Response mode injection
  → Hermes response
  → GBrain log/update
```

---

## Status

| Phase | Description | Status |
|---|---|---|
| 0 | Project bootstrapping | ✅ |
| 1 | GBrain storage layer | ✅ |
| 2 | Operating contract | ✅ |
| 3 | Embedding + retrieval (OpenAI `text-embedding-3-small`) | ✅ |
| 4 | Rule engine (7 risk types) | ✅ |
| 5 | Cheap critic layer (JSON-only LLM judge) | ✅ |
| 6 | Reflex middleware | ✅ |
| 7 | Telegram commands | ✅ |
| 8 | Pattern lifecycle (candidate → watching → active → retired) | ✅ |
| 9 | Weekly review generator | ✅ |
| 10 | Skillify candidates | ✅ |

**336/336 tests passing**

---

## Response Modes

| Mode | When it's used |
|---|---|
| `ALLOW` | No risk detected |
| `NOTE` | Soft caution, weak evidence |
| `CHALLENGE` | Moderate conflict, evidence available |
| `CLARIFY` | Unclear intent, ask one question |
| `REQUIRE_OVERRIDE` | Direct contract or experiment violation |
| `SILENT_LOG` | Log only, don't interrupt |

---

## MVP Commands

```
/checkin              — Daily standup
/experiment create    — Create structured experiment
/patterns             — View active/watching patterns
/reflex <question>    — Run middleware manually
/review               — Weekly review
/override             — Continue after challenge
/reflex pause today   — Pause proactive interventions
/reflex resume        — Resume interventions
```

---

## Quick Start

```bash
git clone https://github.com/sprajapati024/Hermes-Reflex
cd Hermes-Reflex

pip install -r requirements.txt

export OPENAI_API_KEY="sk-..."
export HERMES_REFLEX_GBRAIN_ROOT="~/gbrain"

PYTHONPATH=src python3 -m pytest  # run tests
```

---

## Project Structure

```
Hermes-Reflex/
├── src/
│   ├── core/           — middleware, rule_engine, operating_contract,
│   │                      response_modes, schemas, config, pause
│   ├── gbrain/         — storage, paths, frontmatter, markdown
│   ├── embeddings/     — openai_client, chunker, indexer, search, manifest
│   ├── patterns/       — rules, detector, lifecycle, evidence
│   ├── critic/         — prompt, client, parser, decision
│   ├── commands/       — router, checkin, experiment, patterns, reflex,
│   │                      review, override, pause
│   ├── reviews/        — weekly
│   ├── interventions/  — skillify
│   └── experiments/    — (referenced by commands/experiments.py)
├── tests/              — 336 tests across all modules
├── scripts/            — rebuild_index.py, update_changed.py
├── config.yaml
├── requirements.txt
├── README.md
├── IMPLEMENTATION_PLAN.md
├── AGENTS.md
├── PRD.md
├── QA_AUDIT.md
└── USER_STORIES.md
```

---

## No Dashboard Rule

The first experiment running inside Hermes Reflex:

```
No Dashboard Build
```

Success criteria: ship `/experiment`, `/checkin`, `/patterns`, `/reflex` before any dashboard or UI work.

---

## Docs

- [PRD.md](./PRD.md) — Product requirements
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) — Phase-by-phase build guide
- [QA_AUDIT.md](./QA_AUDIT.md) — Theory audit and loophole fixes
- [USER_STORIES.md](./USER_STORIES.md) — User flows and experience
- [AGENTS.md](./AGENTS.md) — Agent build instructions and operating rules
