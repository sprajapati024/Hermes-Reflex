# Hermes Reflex — Agent Build Instructions

**Audience:** AI coding agents working inside this repository.
**Role:** Build instructions, not brainstorming.
**Project status:** Locked v1 architecture.
**Embedding model:** OpenAI `text-embedding-3-small`.
**Primary interface:** Telegram.
**Memory system:** GBrain.
**Main rule:** No dashboard before the Reflex loop works.

---

## Build Principle

Build Hermes Reflex as an anti-yes-man middleware.

The system runs before or beside the normal Hermes response and decides whether Hermes should:

```
ALLOW | NOTE | CHALLENGE | CLARIFY | REQUIRE_OVERRIDE | SILENT_LOG
```

Do not build a dashboard. Do not build a frontend. Do not create a separate product shell. Do not fork Hermes unless there is no other integration path.

The first working version must prove this loop:

```
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

## Build Order — Do Not Deviate

1. Project shell (this phase)
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

## Context7 Rule

Before writing any code, query `mcp_context7_query_docs` for the relevant library docs.

Required lookups before each module:
- `pyyaml` — config loading
- `openai` — embeddings client
- `sqlite3` — vector index
- `pytest` — testing

## Code Style

- Use typed Python (gradual typing preferred).
- Each module has a single responsibility.
- No hardcoded secrets — use `os.environ` or `.env`.
- Markdown files use YAML frontmatter for structured metadata.
- JSON-only output from the critic layer — never prose.

## File Structure

```
src/
  commands/   — Telegram command handlers
  core/       — Middleware, response modes, config, schemas, logger
  gbrain/     — GBrain markdown storage utilities
  embeddings/ — OpenAI embedding + SQLite vector index
  critic/     — Cheap LLM JSON critic
  patterns/   — Rule engine + pattern lifecycle
  experiments/ — Experiment CRUD
  reviews/    — Weekly review generation
  interventions/ — Override and pause controls
tests/
  Unit tests per module
```

## First Experiment

The first experiment to run inside Hermes Reflex is:

```
No Dashboard Build
```

Success criteria:

```
Ship /experiment, /checkin, /patterns, and /reflex before any dashboard or UI work.
```
