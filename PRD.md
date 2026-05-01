# Product Requirements Document: Hermes Reflex

**Status:** Locked v1 planning spec  
**Primary interface:** Telegram  
**Runtime:** Hermes  
**Memory system:** GBrain  
**Embedding provider:** OpenAI API  
**Embedding model:** `text-embedding-3-small`  
**Core product type:** Anti-yes-man reflex middleware

---

## 1. Product Name

# Hermes Reflex

### Tagline

A Telegram-native anti-yes-man middleware for Hermes + GBrain.

---

## 2. Product Summary

Hermes Reflex is a middleware layer that runs before or beside Hermes responses.

Its job is to prevent Hermes from blindly agreeing with user requests that conflict with the user's stated goals, active experiments, current operating contract, or known execution patterns.

Hermes Reflex uses:

1. deterministic rules,
2. GBrain markdown memory,
3. OpenAI `text-embedding-3-small` retrieval,
4. a cheap critic LLM that returns structured JSON,
5. response-mode injection into the main Hermes model,
6. GBrain logging and review loops.

The result is a Hermes agent that can comply when appropriate, but push back when the request is likely to create scope creep, planning loops, UI avoidance, project switching, or other known failure modes.

Hermes Reflex is not another dashboard. It is the spine Hermes uses before it says yes.

---

## 3. Problem Statement

Most LLMs are eager to please. They are optimized to answer, comply, and reduce friction.

That becomes a problem when the user asks for something that feels productive but conflicts with the user's actual goals.

Examples:

- "Let's rewrite the PRD again."
- "Maybe we need a dashboard."
- "Let's add integrations before the core command works."
- "Let's start a new repo."
- "Let's make the MVP more advanced."

A standard assistant will usually help. Very polite. Very useless. A golden retriever with token billing.

Hermes Reflex solves this by adding an evidence-backed critic layer before Hermes responds.

---

## 4. Product Thesis

The user does not need an AI that always says yes.

The user needs an AI that knows when yes would sabotage the user's higher-order goals.

### Core thesis

> Hermes Reflex protects the user's operating contract from short-term impulses by using memory retrieval, pattern detection, and critic-mode response gating.

---

## 5. Goals

### Primary Goals

1. Detect when a user request conflicts with active goals, experiments, patterns, or operating contracts.
2. Retrieve relevant evidence from GBrain using OpenAI embeddings.
3. Classify the request using a cheap critic model.
4. Select the correct response mode: allow, note, challenge, clarify, require override, or silent log.
5. Inject the response mode into the main Hermes response.
6. Log interventions, overrides, experiments, check-ins, and reviews to GBrain.
7. Convert repeated useful interventions into durable skills.

### Secondary Goals

1. Reduce planning loops.
2. Reduce UI/dashboard avoidance.
3. Reduce premature scope expansion.
4. Improve shipping behavior.
5. Preserve the user's agency through overrides and pause controls.

---

## 6. Non-Goals

Hermes Reflex v1 will not include:

- dashboard
- frontend
- React app
- Tailwind UI
- SaaS auth
- multi-user support
- mobile app
- replacing Hermes
- replacing GBrain
- embedding the entire GBrain repo
- full ML classifier
- complex vector database infrastructure
- calendar/Gmail integrations
- autonomous destructive actions

The only database-like addition allowed in v1 is a lightweight local embedding index for Reflex retrieval.

---

## 7. Target User

Primary user: Shirin.

Context:

- Uses Hermes through Telegram.
- Hosts Hermes on VPS.
- Uses GBrain as the memory layer.
- Builds multiple software/workflow projects.
- Wants AI that pushes back instead of blindly agreeing.
- Wants this to be challenging enough to learn from.

---

## 8. Locked Architecture

```txt
Telegram message
  -> Hermes Gateway
  -> Hermes Reflex Middleware
     -> command detector
     -> rules engine
     -> operating contract checker
     -> embedding query generator
     -> OpenAI text-embedding-3-small
     -> vector/evidence retrieval
     -> cheap critic LLM JSON decision
     -> response mode selector
  -> Hermes Main LLM
  -> Telegram response
  -> GBrain write/update
```

---

## 9. Response Modes

Hermes Reflex must classify each meaningful user message into one of these modes:

```txt
ALLOW
NOTE
CHALLENGE
CLARIFY
REQUIRE_OVERRIDE
SILENT_LOG
```

### ALLOW

No conflict detected. Hermes responds normally.

### NOTE

Minor risk detected. Hermes adds a soft caution but still helps.

### CHALLENGE

Moderate/high conflict detected. Hermes must push back before helping.

### CLARIFY

Request is ambiguous and could conflict with goals. Hermes asks for one clarification or proposes a constrained path.

### REQUIRE_OVERRIDE

Request directly conflicts with an active operating contract or experiment. Hermes must require explicit override before proceeding.

### SILENT_LOG

Signal is useful for future pattern detection, but no user-facing pushback is needed.

---

## 10. Embedding and Retrieval Requirements

### 10.1 Chosen Model

Use OpenAI:

```yaml
provider: openai
model: text-embedding-3-small
default_dimensions: 1536
```

### 10.2 Retrieval Scope

Embed only Reflex-relevant memory.

Allowed folders:

```txt
gbrain/reflex/patterns/
gbrain/reflex/experiments/
gbrain/reflex/reviews/
gbrain/reflex/checkins/
gbrain/reflex/skillify-candidates/
gbrain/reflex/contracts/
gbrain/projects/active/
```

Do not embed:

```txt
raw logs
full chat dumps
entire repositories
large generated reports
unrelated personal notes
binary files
node_modules
.env files
secrets
```

### 10.3 Retrieval Output

Each retrieval result must include:

```yaml
id: string
path: string
type: pattern | experiment | review | checkin | contract | project_note | skill_candidate
summary: string
score: float
updated_at: string
```

### 10.4 Evidence Rule

No strong pushback without evidence.

If evidence is weak, use `NOTE` or `CLARIFY`, not `CHALLENGE` or `REQUIRE_OVERRIDE`.

---

## 11. Reflex Critic Layer

The critic model must not write the final user response.

It must only return JSON.

### Required JSON Schema

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

### Critic Rules

1. Return JSON only.
2. Do not write final prose.
3. Do not diagnose mental health.
4. Do not moralize.
5. Prefer lower severity when evidence is weak.
6. Require override only for direct contract/experiment conflict.

---

## 12. Operating Contract

Hermes Reflex must support a current operating contract stored in GBrain:

```txt
gbrain/reflex/contracts/current-operating-contract.md
```

Example:

```md
# Current Operating Contract

## Active goal
Ship Hermes Reflex v1.

## Constraints
- No dashboard
- No frontend
- Telegram commands only
- GBrain markdown storage
- Use OpenAI text-embedding-3-small for retrieval

## Reflex authority
Hermes may challenge requests that conflict with this contract.

## Override
The user can override, but overrides are logged.
```

The operating contract is the source of truth for strong pushback.

---

## 13. MVP Commands

### `/checkin`

Logs daily check-in.

### `/experiment create`

Creates an experiment.

### `/patterns`

Shows detected patterns with evidence.

### `/reflex`

Runs the reflex recommendation pipeline manually.

### `/review`

Generates weekly review.

### `/override`

Overrides current challenge.

### `/reflex pause today`

Pauses proactive interventions for the day.

### `/reflex pause week`

Pauses proactive interventions for the week.

### `/reflex resume`

Resumes proactive interventions.

---

## 14. Data Model

### 14.1 Signal

```yaml
id: signal_20260501_001
type: planning_loop
source: telegram
project: hermes-reflex
confidence: 0.76
severity: medium
evidence: User requested another PRD revision before implementation.
created_at: 2026-05-01T20:00:00-04:00
```

### 14.2 Pattern

```yaml
id: pattern_planning_loop
name: Planning Loop
status: active
confidence: 0.84
evidence_count: 5
last_seen: 2026-05-01
intervention: Require one implementation task before more planning.
```

### 14.3 Experiment

```yaml
id: exp_no_dashboard_build
name: No Dashboard Build
status: active
start_date: 2026-05-01
end_date: 2026-05-08
metric: working Telegram commands shipped
success_criteria: 4 commands shipped
```

### 14.4 Critic Decision

```yaml
id: decision_20260501_001
mode: CHALLENGE
risk_type: ui_avoidance
confidence: 0.86
evidence_ids:
  - pattern_ui_avoidance
  - exp_no_dashboard_build
recommended_action: Ship /patterns before dashboard work.
created_at: 2026-05-01T20:15:00-04:00
```

### 14.5 Override

```yaml
id: override_20260501_001
original_decision_id: decision_20260501_001
reason: User explicitly chose to continue.
created_at: 2026-05-01T20:17:00-04:00
```

---

## 15. GBrain File Structure

```txt
gbrain/reflex/
  README.md
  config.yaml

  contracts/
    current-operating-contract.md

  checkins/
    2026/05/2026-05-01.md

  signals/
    2026/05/2026-05-01.md

  decisions/
    2026/05/2026-05-01.md

  patterns/
    candidate/
    watching/
    active/
    retired/

  experiments/
    planned/
    active/
    completed/
    abandoned/

  interventions/
    2026/05/

  overrides/
    2026/05/

  reviews/
    weekly/
    monthly/

  skillify-candidates/

  embeddings/
    index.sqlite
    manifest.json
```

---

## 16. Pattern Lifecycle

```txt
candidate -> watching -> active -> retired
```

Rules:

- Candidate: one weak signal.
- Watching: repeated weak or medium signals.
- Active: repeated evidence and useful intervention available.
- Retired: no longer useful or user retires it.

No pattern becomes active from one signal.

---

## 17. Intervention Rules

1. Max one unsolicited intervention per day.
2. Every intervention must include evidence.
3. Every intervention must include one next action.
4. Every intervention must allow override.
5. Low-confidence signals must not trigger hard pushback.
6. No psychological diagnosis.
7. Pause state must be respected.
8. Strong challenge requires either high-confidence pattern evidence or operating contract conflict.

---

## 18. Success Metrics

### MVP Metrics

- 1 operating contract created.
- 1 embedding index created.
- At least 20 Reflex files embedded.
- `/checkin` works.
- `/experiment create` works.
- `/patterns` works.
- `/reflex` returns critic-backed recommendation.
- `/review` works.
- `/override` works.
- At least 1 challenge decision logged.

### Quality Metrics

- Intervention acceptance rate.
- Override rate.
- False-positive pushbacks.
- Evidence retrieval relevance.
- Weekly review usefulness.
- Number of shipped commands.

---

## 19. Acceptance Criteria

Hermes Reflex v1 is complete when:

1. Telegram commands work.
2. GBrain storage works.
3. OpenAI embedding index works.
4. Retrieval returns relevant Reflex evidence.
5. Critic returns valid JSON.
6. Response mode injection changes Hermes behavior.
7. Challenge/override flow works.
8. Weekly review summarizes decisions, patterns, experiments, and overrides.
9. No dashboard/frontend exists.
10. The system can stop Hermes from blindly agreeing at least once in a real user flow.

---

## 20. Final Definition

Hermes Reflex is a Telegram-native anti-yes-man middleware for Hermes + GBrain.

It uses rules, OpenAI embeddings, retrieved evidence, operating contracts, and a cheap critic model to decide whether Hermes should allow, note, challenge, clarify, require override, or silently log a user request.

Its job is not to be agreeable.

Its job is to help Hermes be loyal to the user's real goals.
