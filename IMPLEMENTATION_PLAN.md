# Hermes Reflex - Locked Implementation Plan

**Audience:** AI coding agents working inside `hermes-workspace`  
**Role of this document:** Build instructions, not brainstorming  
**Project status:** Locked v1 architecture  
**Embedding model:** OpenAI `text-embedding-3-small`  
**Primary interface:** Telegram  
**Memory system:** GBrain  
**Main rule:** No dashboard before the Reflex loop works

---

## 0. Build Principle

Build Hermes Reflex as an anti-yes-man middleware.

The system must run before or beside the normal Hermes response and decide whether Hermes should:

```txt
ALLOW
NOTE
CHALLENGE
CLARIFY
REQUIRE_OVERRIDE
SILENT_LOG
```

Do not build a dashboard. Do not build a frontend. Do not create a separate product shell. Do not fork Hermes unless there is no other integration path.

The first working version must prove this loop:

```txt
Telegram message
  -> Reflex middleware
  -> rules check
  -> operating contract check
  -> OpenAI embedding retrieval
  -> cheap critic JSON decision
  -> response mode injection
  -> Hermes response
  -> GBrain log/update
```

---

## 1. Technical Placement

Create the implementation under:

```txt
hermes-workspace/projects/hermes-reflex/
```

Recommended structure:

```txt
projects/hermes-reflex/
  README.md
  AGENTS.md
  config.yaml
  requirements.txt

  src/
    __init__.py

    commands/
      __init__.py
      checkin.py
      experiment.py
      patterns.py
      reflex.py
      review.py
      override.py
      pause.py

    core/
      __init__.py
      middleware.py
      response_modes.py
      operating_contract.py
      config.py
      schemas.py
      logger.py

    gbrain/
      __init__.py
      paths.py
      markdown.py
      frontmatter.py
      storage.py

    embeddings/
      __init__.py
      openai_client.py
      chunker.py
      indexer.py
      search.py
      manifest.py

    critic/
      __init__.py
      prompt.py
      client.py
      parser.py
      decision.py

    patterns/
      __init__.py
      rules.py
      detector.py
      lifecycle.py
      evidence.py

    experiments/
      __init__.py
      create.py
      evaluate.py
      schema.py

    reviews/
      __init__.py
      weekly.py
      summarizer.py

    interventions/
      __init__.py
      router.py
      override.py
      pause.py

  tests/
    test_gbrain_storage.py
    test_embeddings.py
    test_critic_parser.py
    test_pattern_rules.py
    test_response_modes.py
```

If Hermes has an existing plugin/skill structure, adapt to that structure but preserve these logical modules.

---

## 2. Required Environment Variables

Use environment variables. Do not hardcode secrets, because apparently we still have to remind software not to tattoo API keys onto Git history.

```bash
OPENAI_API_KEY="..."
HERMES_REFLEX_GBRAIN_PATH="/path/to/gbrain"
HERMES_REFLEX_INDEX_PATH="/path/to/gbrain/reflex/embeddings/index.sqlite"
HERMES_REFLEX_ENABLED="true"
HERMES_REFLEX_CRITIC_MODEL="cheap-model-name"
HERMES_REFLEX_MAIN_PROJECT="hermes-reflex"
```

Optional:

```bash
HERMES_REFLEX_MAX_DAILY_INTERVENTIONS="1"
HERMES_REFLEX_EMBEDDING_MODEL="text-embedding-3-small"
HERMES_REFLEX_EMBEDDING_DIMENSIONS="1536"
```

---

## 3. GBrain Target Structure

Agent must create this structure if missing:

```txt
gbrain/reflex/
  README.md
  config.yaml

  contracts/
    current-operating-contract.md

  checkins/
  signals/
  decisions/
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
  overrides/
  reviews/
    weekly/
    monthly/
  skillify-candidates/
  embeddings/
    index.sqlite
    manifest.json
```

---

## 4. Phase 0 - Project Bootstrapping

### Goal

Create the Hermes Reflex project shell and configuration.

### Tasks

1. Create `projects/hermes-reflex/` folder.
2. Create `README.md` explaining local setup.
3. Create `AGENTS.md` with build rules for future agents.
4. Create `config.yaml` with defaults.
5. Create `requirements.txt` or use the repo's existing dependency manager.
6. Create Python package folders under `src/`.
7. Add `.gitignore` entries if needed for local index/cache files.

### Required `config.yaml`

```yaml
project: hermes-reflex
interface: telegram
runtime: hermes
memory: gbrain

reflex:
  enabled: true
  max_unsolicited_interventions_per_day: 1
  default_response_mode: ALLOW
  require_evidence_for_challenge: true

openai_embeddings:
  provider: openai
  model: text-embedding-3-small
  dimensions: 1536
  batch_size: 100

retrieval:
  top_k: 8
  min_score: 0.65
  allowed_paths:
    - reflex/patterns
    - reflex/experiments
    - reflex/reviews
    - reflex/checkins
    - reflex/skillify-candidates
    - reflex/contracts
    - projects/active

critic:
  output_format: json_only
  allow_override_default: true
```

### Acceptance Criteria

- Project folder exists.
- Config loads without errors.
- No dashboard/frontend files are created.

---

## 5. Phase 1 - GBrain Storage Layer

### Goal

Build reliable markdown read/write utilities for Reflex data.

### Tasks

1. Implement path resolver in `gbrain/paths.py`.
2. Implement frontmatter parser/writer in `gbrain/frontmatter.py`.
3. Implement markdown file writer in `gbrain/markdown.py`.
4. Implement storage functions in `gbrain/storage.py`.
5. Ensure date-based directories are created automatically.
6. Add tests for all storage functions.

### Required Functions

```python
ensure_reflex_structure() -> None
write_checkin(data: dict) -> Path
write_signal(data: dict) -> Path
write_decision(data: dict) -> Path
write_experiment(data: dict, status: str = "active") -> Path
write_intervention(data: dict) -> Path
write_override(data: dict) -> Path
write_weekly_review(data: dict) -> Path
read_active_experiments() -> list[dict]
read_active_patterns() -> list[dict]
read_current_contract() -> dict
```

### Acceptance Criteria

- Running `ensure_reflex_structure()` creates missing folders.
- Markdown files include YAML frontmatter.
- Tests prove files can be written and read back.

---

## 6. Phase 2 - Operating Contract

### Goal

Create the contract Reflex uses to justify strong pushback.

### Tasks

1. Implement `core/operating_contract.py`.
2. Add default contract creation if missing.
3. Add parser for active goals, constraints, and override policy.
4. Add conflict checker.

### Default Contract

Create this file:

```txt
gbrain/reflex/contracts/current-operating-contract.md
```

Content:

```md
---
id: current-operating-contract
status: active
updated_at: auto
---

# Current Operating Contract

## Active Goal
Ship Hermes Reflex v1.

## Constraints
- No dashboard
- No frontend
- Telegram commands only
- GBrain markdown storage
- Use OpenAI text-embedding-3-small for retrieval
- No new integrations before core commands work

## Reflex Authority
Hermes Reflex may challenge requests that conflict with this contract.

## Override Policy
The user can override, but overrides must be logged.
```

### Required Function

```python
check_contract_conflict(user_message: str, contract: dict) -> dict
```

Return:

```json
{
  "conflict": true,
  "constraint": "No dashboard",
  "confidence": 0.9,
  "recommended_mode": "REQUIRE_OVERRIDE"
}
```

### Acceptance Criteria

- Contract file is created if missing.
- Contract conflicts are detected for obvious cases like dashboard/frontend/new integration requests.

---

## 7. Phase 3 - OpenAI Embedding Retrieval Layer

### Goal

Build the evidence retrieval system using OpenAI `text-embedding-3-small`.

### Tasks

1. Implement OpenAI embedding client in `embeddings/openai_client.py`.
2. Implement markdown chunking in `embeddings/chunker.py`.
3. Implement SQLite vector index in `embeddings/indexer.py`.
4. Implement retrieval in `embeddings/search.py`.
5. Implement manifest tracking in `embeddings/manifest.py`.
6. Add command/script to rebuild index.
7. Add command/script to update changed files only.

### Embedding Scope

Only index these folders:

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
full repo files
node_modules
binary files
large generated reports
```

### SQLite Tables

If using SQLite, create:

```sql
CREATE TABLE IF NOT EXISTS reflex_documents (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  type TEXT NOT NULL,
  title TEXT,
  content TEXT NOT NULL,
  summary TEXT,
  updated_at TEXT,
  content_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reflex_embeddings (
  document_id TEXT PRIMARY KEY,
  model TEXT NOT NULL,
  dimensions INTEGER NOT NULL,
  embedding_json TEXT NOT NULL,
  embedded_at TEXT NOT NULL
);
```

If sqlite-vec is available, use it. If not, JSON vectors with cosine similarity are acceptable for v1 because the dataset is small. Do not summon a distributed vector database for 200 markdown notes. That would be infrastructure cosplay.

### Required Functions

```python
embed_text(text: str) -> list[float]
chunk_markdown(path: Path) -> list[dict]
index_reflex_memory() -> dict
update_changed_embeddings() -> dict
search_reflex_memory(query: str, top_k: int = 8) -> list[dict]
```

### Acceptance Criteria

- Index can be built from Reflex/GBrain files.
- Query returns top relevant evidence with path, type, score, and summary.
- OpenAI API key is loaded from environment only.
- No secrets are embedded.

---

## 8. Phase 4 - Rule Engine ✓

**Status:** Complete — commit `7cc5fe5`

### Goal

Catch obvious risks without using an LLM.

### Tasks

1. Implement `patterns/rules.py`.
2. Add keyword/phrase rules for MVP patterns.
3. Add contract conflict shortcut.
4. Add active experiment conflict checks.
5. Return structured rule result.

### MVP Risk Types

```txt
planning_loop
ui_avoidance
project_switching
integration_avoidance
overbuild_risk
contract_conflict
```

### Example Rules

Planning loop terms:

```txt
redo PRD
rewrite spec
rethink roadmap
pivot again
make it more advanced
start from scratch
```

UI avoidance terms:

```txt
dashboard
frontend
React
Tailwind
UI polish
design system
visualize patterns
```

Overbuild terms:

```txt
multi-user
SaaS
auth
calendar integration
Gmail integration
analytics
mobile app
vector DB
```

### Required Function

```python
evaluate_rules(user_message: str, context: dict) -> dict
```

Return:

```json
{
  "risk_flags": ["ui_avoidance"],
  "confidence": 0.78,
  "recommended_mode": "CHALLENGE",
  "matched_terms": ["dashboard"]
}
```

### Acceptance Criteria

- Rules detect obvious scope creep.
- Rules do not directly write final responses.
- Rules feed critic/middleware.

---

## 9. Phase 5 - Cheap Critic Layer ✓

**Status:** Complete — built in this session

### Goal

Use a cheaper LLM as a structured judge, not a final writer.

### Tasks

1. Implement critic prompt in `critic/prompt.py`.
2. Implement critic client wrapper in `critic/client.py`.
3. Implement JSON parser/validator in `critic/parser.py`.
4. Implement decision object in `critic/decision.py`.
5. Add retry/fallback if invalid JSON is returned.
6. Add tests with mocked critic responses.

### Critic Input

Pass only compact context:

```json
{
  "user_message": "Let's add a dashboard",
  "rule_result": {},
  "contract_conflict": {},
  "active_experiments": [],
  "retrieved_evidence": [],
  "recent_patterns": []
}
```

### Required Critic Output

```json
{
  "mode": "CHALLENGE",
  "risk_type": "ui_avoidance",
  "confidence": 0.86,
  "severity": "medium",
  "evidence_ids": ["exp_no_dashboard_build", "pattern_ui_avoidance"],
  "reason": "The request conflicts with the active no-dashboard constraint.",
  "recommended_action": "Finish /patterns before dashboard work.",
  "allow_override": true
}
```

### Critic Rules

- JSON only.
- No final prose.
- No diagnosis.
- No moralizing.
- Prefer `NOTE`/`CLARIFY` when evidence is weak.
- Use `REQUIRE_OVERRIDE` only when active contract or experiment is directly violated.

### Acceptance Criteria

- Critic returns valid JSON.
- Invalid critic JSON is handled gracefully.
- Critic decision is logged to GBrain.

---

## 10. Phase 6 - Reflex Middleware

### Goal

Build the central middleware that connects rules, retrieval, critic, response-mode injection, and logging.

### Tasks

1. Implement `core/middleware.py`.
2. Accept incoming user message and context.
3. Run command detector.
4. Run rule engine.
5. Load operating contract.
6. Search embedding index for evidence.
7. Call critic model.
8. Select response mode.
9. Create response instruction for Hermes main model.
10. Log decision to GBrain.

### Required Function

```python
process_reflex(user_message: str, context: dict) -> dict
```

Return:

```json
{
  "mode": "CHALLENGE",
  "risk_type": "ui_avoidance",
  "confidence": 0.86,
  "evidence": [],
  "hermes_instruction": "Challenge first. Cite evidence. Offer one concrete next action. Allow override.",
  "decision_id": "decision_20260501_001"
}
```

### Response Mode Instructions

#### ALLOW

```txt
Respond normally.
```

#### NOTE

```txt
Help the user, but include one short caution based on Reflex evidence.
```

#### CHALLENGE

```txt
Do not immediately comply. First challenge the request using Reflex evidence. Then give one concrete better action. Offer override.
```

#### CLARIFY

```txt
Ask one targeted clarification or propose the safest constrained path.
```

#### REQUIRE_OVERRIDE

```txt
Do not proceed until user explicitly overrides. Explain the conflict and offer the recommended alternative.
```

#### SILENT_LOG

```txt
Respond normally. Do not mention Reflex.
```

### Acceptance Criteria

- Middleware produces a valid Hermes instruction.
- Middleware logs decision.
- Middleware respects pause state.
- Middleware does not block manual commands.

---

## 11. Phase 7 - Telegram Commands

### Goal

Expose Reflex through Telegram commands.

### Commands to Implement

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

### Task Details

#### `/checkin`

Ask:

1. Energy 1-10?
2. Available time?
3. Biggest friction?
4. Main focus?
5. What shipped?
6. What got avoided?

Write to:

```txt
gbrain/reflex/checkins/YYYY/MM/YYYY-MM-DD.md
```

#### `/experiment create`

Create structured experiment under:

```txt
gbrain/reflex/experiments/active/
```

#### `/patterns`

Return active/watching patterns with evidence.

#### `/reflex`

Run middleware manually and return recommendation.

#### `/review`

Generate weekly review.

#### `/override`

Continue after challenge and log override.

### Acceptance Criteria

- Commands work through Telegram.
- Each command writes to GBrain where appropriate.
- Commands are short and usable on mobile.

---

## 12. Phase 8 - Pattern Lifecycle

### Goal

Promote raw signals into useful patterns.

### Tasks

1. Implement `patterns/detector.py`.
2. Implement `patterns/evidence.py`.
3. Implement `patterns/lifecycle.py`.
4. Add status transitions.
5. Update pattern files with evidence.

### Lifecycle

```txt
candidate -> watching -> active -> retired
```

### Promotion Rules

Candidate to watching:

```txt
At least 2 related signals in 14 days.
```

Watching to active:

```txt
At least 3 related signals + one useful intervention available.
```

Active to retired:

```txt
No firing for 30 days or user retires it.
```

### Acceptance Criteria

- Pattern files update over time.
- No pattern becomes active from one weak signal.
- Pattern pages include evidence.

---

## 13. Phase 9 - Weekly Review

### Goal

Generate a useful weekly review from check-ins, decisions, patterns, experiments, and overrides.

### Tasks

1. Implement `reviews/weekly.py`.
2. Pull current week's Reflex files.
3. Summarize shipped work.
4. Summarize stalled/avoided work.
5. Summarize interventions and overrides.
6. Evaluate active experiments.
7. Recommend one next-week experiment or operating rule.
8. Write review to GBrain.

### Required Output Sections

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

### Acceptance Criteria

- Weekly review is evidence-backed.
- Review updates experiment status if needed.
- Review does not sound like generic self-help mush.

---

## 14. Phase 10 - Skillify Candidates

### Goal

Convert repeated useful interventions into reusable skills.

### Tasks

1. Detect repeated active pattern.
2. Check intervention acceptance/usefulness.
3. Create skillify candidate file.
4. Ask user approval before creating actual skill.

### Trigger

Create skillify candidate when:

```txt
pattern fires >= 5 times
and intervention accepted/useful >= 2 times
and user has not retired pattern
```

### Candidate Path

```txt
gbrain/reflex/skillify-candidates/<skill-name>.md
```

### Acceptance Criteria

- User approval required.
- Candidate includes trigger, checklist, and response behavior.

---

## 15. Test Plan

### Unit Tests

- frontmatter parse/write
- storage paths
- embedding chunker
- embedding manifest hashing
- cosine similarity
- rule engine terms
- critic JSON parser
- response mode mapping
- pause/override state

### Integration Tests

- create operating contract
- index Reflex memory
- search evidence for dashboard query
- critic returns CHALLENGE for dashboard conflict
- middleware generates Hermes instruction
- override logs correctly
- weekly review writes file

### Manual Test Script

1. Create operating contract.
2. Create experiment: `No Dashboard Build`.
3. Index Reflex memory.
4. Send message: `Let's add a dashboard`.
5. Confirm mode is `REQUIRE_OVERRIDE` or `CHALLENGE`.
6. Confirm evidence includes contract or experiment.
7. Override.
8. Confirm override file is written.
9. Run `/review`.
10. Confirm weekly review includes override.

---

## 16. Build Order - Do Not Deviate

Build in this order:

1. Project shell
2. GBrain storage
3. Operating contract
4. OpenAI embedding index
5. Rule engine
6. Critic JSON layer
7. Reflex middleware
8. `/experiment create`
9. `/checkin`
10. `/reflex`
11. `/patterns`
12. `/override` and pause/resume
13. `/review`
14. Pattern lifecycle
15. Skillify candidates

No dashboard. No frontend. No integrations until this works.

---

## 17. Definition of Done

Hermes Reflex v1 is done when:

- Telegram commands work.
- GBrain structure is created.
- OpenAI embeddings index Reflex memory.
- Search retrieves relevant evidence.
- Critic returns valid JSON.
- Middleware produces response-mode instructions.
- Hermes challenges at least one bad request with evidence.
- User can override.
- Weekly review logs decisions and outcomes.
- No dashboard exists.

---

## 18. First Real Scenario to Validate

### Setup

Active contract says:

```txt
No dashboard. No frontend. Telegram commands only.
```

Active experiment:

```txt
No Dashboard Build
```

User says:

```txt
Maybe we should add a dashboard so I can see patterns visually.
```

Expected Reflex decision:

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

Expected Hermes response:

```txt
Reflex is blocking this for now.

Reason:
It conflicts with your active No Dashboard Build contract.

Better move:
Ship /patterns first.

Reply:
1. Build /patterns
2. Park dashboard idea
3. Override
```

If this scenario works, the project has a spine.
