# Hermes Reflex

**Status:** Locked project spec  
**Interface:** Telegram  
**Runtime:** Hermes  
**Memory:** GBrain  
**Embeddings:** OpenAI `text-embedding-3-small`  
**Primary purpose:** Anti-yes-man reflex middleware for Hermes

---

## What This Project Is

Hermes Reflex is a Telegram-native middleware layer that runs before or beside Hermes responses.

Its job is to stop Hermes from blindly agreeing with requests that conflict with the user's goals, active experiments, known patterns, or current operating contract.

Hermes Reflex adds a skeptical, evidence-backed decision layer:

```txt
User message
  -> Telegram
  -> Hermes Reflex middleware
  -> rule checks
  -> OpenAI embedding retrieval
  -> cheap critic decision
  -> response mode injection
  -> Hermes main response
  -> GBrain log/update
```

This is not a dashboard. This is not a generic productivity coach. This is not another memory system. Those ideas are how promising projects go to die wearing nice typography.

Hermes Reflex is the anti-yes-man layer.

---

## Core Thesis

LLMs are usually too eager to comply. That is useful for many tasks, but harmful when the user is repeating a known bad loop: planning instead of building, adding scope before shipping, redesigning instead of testing, or starting another project before finishing the current one.

Hermes Reflex protects the user's higher-order goals from lower-order impulses.

Example:

```txt
User: Let's add a dashboard.

Hermes Reflex:
This conflicts with the active No Dashboard Build experiment and the UI Avoidance pattern.
Challenge first. Offer one implementation action. Allow override.
```

Hermes then responds with controlled pushback instead of cheerful obedience.

---

## Locked Architecture

```txt
Telegram
  -> Hermes Gateway
  -> Reflex Middleware
     -> Command detector
     -> Rule engine
     -> Operating contract checker
     -> Embedding retrieval using OpenAI text-embedding-3-small
     -> Cheap critic model returning JSON
     -> Response mode selector
  -> Hermes Main LLM
  -> Telegram response
  -> GBrain write/update
```

---

## Chosen Embedding Strategy

Use OpenAI API with:

```yaml
embedding_provider: openai
embedding_model: text-embedding-3-small
embedding_dimensions: 1536
```

Only embed Reflex-relevant memory, not the entire universe like a confused intern with a vector database.

Embed these folders:

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
random personal notes unrelated to Reflex
```

---

## MVP Commands

```txt
/checkin
/experiment create
/patterns
/reflex
/review
/override
/reflex pause today
/reflex pause week
/reflex resume
```

---

## Locked MVP Rule

No dashboard.  
No frontend.  
No React.  
No Tailwind.  
No SaaS.  
No extra database beyond the required lightweight embedding index.  
No full ML classifier.

If an agent proposes a dashboard before the core commands work, reject the plan. The robot does not need a glass cockpit before it has a spine.

---

## Documents

- [PRD.md](./PRD.md) - Locked product requirements
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) - Phase-by-phase agent build instructions
- [QA_AUDIT.md](./QA_AUDIT.md) - Theory audit and loophole fixes
- [USER_STORIES.md](./USER_STORIES.md) - User flows and two-month experience
- [AGENT_BUILD_INSTRUCTIONS.md](./AGENT_BUILD_INSTRUCTIONS.md) - Direct build instructions for coding agents

---

## First Experiment

The first experiment to run inside Hermes Reflex is:

```txt
No Dashboard Build
```

Success criteria:

```txt
Ship /experiment, /checkin, /patterns, and /reflex before any dashboard or UI work.
```

---

## Final Definition

Hermes Reflex is a Telegram-native anti-yes-man middleware for Hermes + GBrain. It uses rules, OpenAI embeddings, retrieved evidence, and a cheap critic model to decide when Hermes should comply, challenge, clarify, redirect, or require override.
