# Hermes Reflex - Agent Build Instructions

You are the coding agent implementing Hermes Reflex.

Read this file before touching code.

If your proposed implementation includes a dashboard, frontend, React app, Tailwind UI, SaaS shell, mobile app, or a new memory system, stop. You are solving the wrong problem. Congratulations, you have discovered scope creep. Do not feed it.

---

## Mission

Build Hermes Reflex as a Telegram-native anti-yes-man middleware for Hermes + GBrain.

The system must evaluate user messages before Hermes blindly complies.

Hermes Reflex must decide whether Hermes should:

```txt
ALLOW
NOTE
CHALLENGE
CLARIFY
REQUIRE_OVERRIDE
SILENT_LOG
```

The main goal is to prevent LLM agreeableness from helping the user sabotage higher-order goals.

---

## Locked Stack

```yaml
interface: Telegram
runtime: Hermes
memory: GBrain
embeddings_provider: OpenAI API
embeddings_model: text-embedding-3-small
storage: GBrain markdown + lightweight local SQLite embedding index
critic: cheap LLM returning JSON only
main_llm: existing Hermes response model
```

---

## Non-Negotiable Rules

1. Do not build a dashboard.
2. Do not build frontend UI.
3. Do not fork Hermes unless absolutely required.
4. Do not replace GBrain.
5. Do not embed the entire GBrain repo.
6. Do not hardcode API keys.
7. Do not let the critic write final prose.
8. Do not make psychological/medical diagnoses.
9. Do not block the user permanently. Always allow override unless safety requires refusal.
10. Do not activate a pattern from one weak signal.

---

## Core Runtime Flow

Implement this exact flow:

```txt
Telegram message
  -> Hermes Reflex middleware
  -> command detection
  -> operating contract check
  -> deterministic rule check
  -> embedding retrieval from GBrain Reflex memory
  -> cheap critic model JSON decision
  -> response mode instruction
  -> Hermes main LLM response
  -> GBrain log/update
```

---

## Phase 1 - Project Shell

Create:

```txt
projects/hermes-reflex/
  README.md
  AGENTS.md
  config.yaml
  requirements.txt
  src/
  tests/
```

Minimum folders inside `src/`:

```txt
commands/
core/
gbrain/
embeddings/
critic/
patterns/
experiments/
reviews/
interventions/
```

Acceptance:

- Project imports without error.
- Config loads.
- No dashboard/frontend files exist.

---

## Phase 2 - GBrain Storage

Create GBrain structure:

```txt
gbrain/reflex/
  contracts/
  checkins/
  signals/
  decisions/
  patterns/candidate/
  patterns/watching/
  patterns/active/
  patterns/retired/
  experiments/planned/
  experiments/active/
  experiments/completed/
  experiments/abandoned/
  interventions/
  overrides/
  reviews/weekly/
  reviews/monthly/
  skillify-candidates/
  embeddings/
```

Implement:

```python
ensure_reflex_structure()
write_checkin(data)
write_signal(data)
write_decision(data)
write_experiment(data, status="active")
write_intervention(data)
write_override(data)
write_weekly_review(data)
read_active_experiments()
read_active_patterns()
read_current_contract()
```

Acceptance:

- Files are markdown.
- Files include YAML frontmatter.
- Date-based directories are created automatically.

---

## Phase 3 - Operating Contract

Create default contract at:

```txt
gbrain/reflex/contracts/current-operating-contract.md
```

Default constraints:

```txt
- No dashboard
- No frontend
- Telegram commands only
- GBrain markdown storage
- Use OpenAI text-embedding-3-small for retrieval
- No new integrations before core commands work
```

Implement:

```python
check_contract_conflict(user_message, contract)
```

Acceptance:

- Dashboard/frontend requests create contract conflict.
- Contract conflict recommends `REQUIRE_OVERRIDE` or `CHALLENGE`.

---

## Phase 4 - OpenAI Embedding Retrieval

Use OpenAI:

```txt
text-embedding-3-small
```

Only index:

```txt
gbrain/reflex/patterns/
gbrain/reflex/experiments/
gbrain/reflex/reviews/
gbrain/reflex/checkins/
gbrain/reflex/skillify-candidates/
gbrain/reflex/contracts/
gbrain/projects/active/
```

Never index:

```txt
.env
secrets
raw logs
full repos
node_modules
binary files
large generated reports
```

Implement:

```python
embed_text(text)
chunk_markdown(path)
index_reflex_memory()
update_changed_embeddings()
search_reflex_memory(query, top_k=8)
```

Acceptance:

- Index builds.
- Search returns relevant evidence.
- Results include path, type, score, summary.
- OpenAI key comes only from env.

---

## Phase 5 - Rule Engine

Implement deterministic rules first.

Risk types:

```txt
planning_loop
ui_avoidance
project_switching
integration_avoidance
overbuild_risk
contract_conflict
```

Implement:

```python
evaluate_rules(user_message, context)
```

Acceptance:

- Obvious dashboard/frontend/scope creep language is caught without LLM.
- Rule output is structured.
- Rules do not generate final prose.

---

## Phase 6 - Critic JSON Layer

The critic model is a judge, not a writer.

It must return only:

```json
{
  "mode": "ALLOW | NOTE | CHALLENGE | CLARIFY | REQUIRE_OVERRIDE | SILENT_LOG",
  "risk_type": "none | planning_loop | ui_avoidance | project_switching | integration_avoidance | overbuild_risk | contract_conflict | other",
  "confidence": 0.0,
  "severity": "low | medium | high",
  "evidence_ids": [],
  "reason": "short explanation",
  "recommended_action": "one concrete next action",
  "allow_override": true
}
```

Implement:

```python
build_critic_prompt(context)
call_critic(prompt)
parse_critic_decision(raw)
validate_critic_decision(decision)
```

Acceptance:

- Invalid JSON is handled.
- Critic never writes final user response.
- Critic decision is logged.

---

## Phase 7 - Reflex Middleware

Implement:

```python
process_reflex(user_message: str, context: dict) -> dict
```

Output:

```json
{
  "mode": "CHALLENGE",
  "risk_type": "ui_avoidance",
  "confidence": 0.86,
  "evidence": [],
  "hermes_instruction": "Challenge first. Cite evidence. Offer one concrete next action. Allow override.",
  "decision_id": "decision_..."
}
```

Acceptance:

- Middleware creates response-mode instruction.
- Middleware respects pause state.
- Middleware logs decision.
- Middleware can be called before main Hermes response.

---

## Phase 8 - Telegram Commands

Implement commands:

```txt
/checkin
/experiment create <name>
/patterns
/reflex <question>
/review
/override
/reflex pause today
/reflex pause week
/reflex resume
```

Acceptance:

- Commands work in Telegram.
- Commands write to GBrain.
- Commands are mobile-friendly and short.

---

## Phase 9 - Pattern Lifecycle

Lifecycle:

```txt
candidate -> watching -> active -> retired
```

Promotion rules:

```txt
candidate -> watching: 2 related signals in 14 days
watching -> active: 3 related signals + useful intervention exists
active -> retired: no firing for 30 days or user retires it
```

Acceptance:

- No pattern becomes active from one weak signal.
- Active pattern files include evidence.

---

## Phase 10 - Weekly Review

Implement `/review`.

Required sections:

```txt
What shipped
What stalled
Patterns fired
Interventions accepted
Overrides logged
Experiment results
Next week recommendation
One thing to stop doing
```

Acceptance:

- Review is written to GBrain.
- Review includes evidence.
- Review updates experiments when needed.

---

## First Validation Scenario

Set active contract:

```txt
No dashboard. No frontend. Telegram commands only.
```

Create active experiment:

```txt
No Dashboard Build
```

Input:

```txt
Maybe we should add a dashboard so I can see patterns visually.
```

Expected critic decision:

```json
{
  "mode": "REQUIRE_OVERRIDE",
  "risk_type": "contract_conflict",
  "confidence": 0.9,
  "severity": "high",
  "recommended_action": "Finish /patterns and /review before any dashboard work.",
  "allow_override": true
}
```

Expected Hermes behavior:

```txt
Reflex blocks dashboard work for now because it conflicts with the active contract.
Recommended action: ship /patterns first.
Options: build /patterns, park dashboard idea, or override.
```

---

## Final Definition of Done

Hermes Reflex v1 is complete only when:

- It can challenge a bad request before Hermes agrees.
- It can cite evidence from GBrain retrieval.
- It can log the critic decision.
- It can allow and log override.
- It can generate a weekly review.
- It has no dashboard.

Anything else is decoration. Do not decorate a machine that does not work yet.
