# Hermes Reflex - QA / Theory Audit

**Status:** Locked audit for v1  
**Architecture:** Telegram + Hermes + GBrain + OpenAI embeddings + cheap critic JSON layer  
**Main risk:** Building a polite productivity toy instead of an anti-yes-man middleware

---

## 1. Executive Verdict

Hermes Reflex is worth building only if it solves the real problem:

> Hermes must stop blindly agreeing when the user request conflicts with the user's goals, operating contract, active experiments, or known patterns.

The project fails if it becomes:

- a dashboard
- a generic productivity bot
- another memory system
- a motivational coach
- a vague self-improvement assistant
- a full ML science project
- a noisy nagging assistant

The project works if it becomes:

> A Telegram-native anti-yes-man middleware that uses rules, OpenAI embedding retrieval, a cheap critic model, and GBrain evidence to decide whether Hermes should comply, challenge, clarify, require override, or silently log.

---

## 2. Product Name Audit

### Final Name: Hermes Reflex

Why this works:

- Ties directly into Hermes.
- Implies fast response, not passive tracking.
- Fits middleware better than a separate SaaS brand.
- Avoids tired names like dashboard, command center, copilot, assistant, brain, or OS.

Future productized name, if needed:

```txt
LifeLab
```

But for now, lock the project as:

```txt
Hermes Reflex
```

---

## 3. Updated Theory Audit

### Old theory

Hermes Reflex detects patterns and runs experiments.

### Stronger locked theory

Hermes Reflex prevents LLM agreeableness from sabotaging the user's higher-order goals.

This is stronger because it gives the system a specific job:

```txt
Before Hermes says yes, check whether yes is actually harmful.
```

That is the core product spine.

---

## 4. Core Assumptions

### Assumption 1: Telegram remains the primary interface

**Status:** Strong.

The user already uses Telegram to talk to Hermes. A dashboard would create more surface area without solving the yes-man problem.

**Risk:** Multi-step Telegram flows can become annoying.

**Mitigation:** Keep commands short. Use one decision per message. Use override/pause controls.

---

### Assumption 2: GBrain remains the memory system

**Status:** Strong.

GBrain already stores durable memory. Hermes Reflex should write structured markdown into GBrain and use embeddings for retrieval.

**Risk:** Reflex pollutes GBrain with low-value tiny files.

**Mitigation:** Use compact daily logs for raw signals and curated files for patterns, experiments, contracts, and reviews.

---

### Assumption 3: OpenAI `text-embedding-3-small` is the right embedding model

**Status:** Strong for v1.

Reasons:

- Low operational complexity.
- Good enough for Reflex evidence retrieval.
- Cheaper and simpler than running local embeddings on the VPS.
- Avoids spending build time on model hosting.

**Risk:** Embedding irrelevant content creates noisy retrieval.

**Mitigation:** Do not embed all of GBrain. Only embed Reflex-relevant folders and active project notes.

---

### Assumption 4: Cheap critic model should judge, not write

**Status:** Critical.

The critic model should return JSON only. The main Hermes model writes the actual response after receiving response-mode instructions.

**Risk:** If the critic writes prose, it becomes another assistant layer and starts producing generic advice sludge.

**Mitigation:** Validate critic JSON. Retry or fall back to rules when invalid.

---

### Assumption 5: Pushback must be evidence-backed

**Status:** Non-negotiable.

Without evidence, Reflex becomes annoying and untrustworthy.

**Mitigation:** Strong challenge requires at least one of:

- operating contract conflict,
- active experiment conflict,
- high-confidence pattern,
- retrieved evidence from GBrain.

---

## 5. Major Loopholes and Fixes

### Loophole 1: It becomes a nagging assistant

Bad:

```txt
You are avoiding implementation again.
```

Good:

```txt
Reflex is flagging Planning Loop.
Evidence: You asked for another PRD rewrite before shipping /patterns.
Recommended action: ship /patterns first.
Options: build /patterns, park idea, override.
```

**Fix:** Every challenge must include evidence, one next action, and override.

---

### Loophole 2: The critic becomes another yes-man

A cheap critic model may still agree unless constrained.

**Fix:** The critic must be given structured options only:

```txt
ALLOW, NOTE, CHALLENGE, CLARIFY, REQUIRE_OVERRIDE, SILENT_LOG
```

It must return JSON only.

---

### Loophole 3: The system overuses CHALLENGE

If every idea gets challenged, the user will hate it and disable it.

**Fix:** Use disagreement levels:

```txt
ALLOW: no risk
NOTE: small caution
CHALLENGE: moderate conflict
REQUIRE_OVERRIDE: direct contract/experiment conflict
SILENT_LOG: useful signal, no user interruption
```

Max one unsolicited intervention per day.

---

### Loophole 4: Retrieval returns weak or unrelated evidence

Embedding search is useful, not magical. Shocking, the math rectangle does not understand your soul.

**Fix:** Retrieval results must include type, path, score, and summary. Critic must prefer lower-severity modes when evidence is weak.

---

### Loophole 5: The system embeds secrets or junk

Embedding everything is lazy and risky.

**Fix:** Hard denylist:

```txt
.env
secrets
raw logs
full repo files
node_modules
binary files
large generated reports
```

Allowed list only:

```txt
reflex/patterns
reflex/experiments
reflex/reviews
reflex/checkins
reflex/contracts
reflex/skillify-candidates
projects/active
```

---

### Loophole 6: Operating contract becomes stale

If the contract says "No dashboard" forever, it may block valid future work.

**Fix:** Weekly review must include contract review when an override happens repeatedly.

Rule:

```txt
If user overrides same contract constraint 3 times, suggest revising the contract.
```

---

### Loophole 7: Reflex confuses repeated interest with failure pattern

Talking about fitness often does not mean avoidance. It may be a real goal.

**Fix:** Classify repetition as:

```txt
failure_pattern
active_goal
recurring_interest
unresolved_decision
maintenance_routine
```

Do not treat all repetition as failure. That would be dumb with confidence, the most dangerous software genre.

---

### Loophole 8: Pattern activation is too easy

One message should not create an active pattern.

**Fix:** Pattern lifecycle:

```txt
candidate -> watching -> active -> retired
```

No active pattern without repeated evidence.

---

### Loophole 9: The system blocks creativity

Sometimes a pivot is correct.

**Fix:** Reflex should challenge, not imprison. Override must be available. If overrides repeatedly happen and lead to good outcomes, Reflex should update the pattern.

---

### Loophole 10: Weekly reviews become generic nonsense

Bad weekly review:

```txt
Great job this week. Keep going.
```

Absolutely useless. A motivational fridge magnet with latency.

Good weekly review:

```txt
What shipped:
- /experiment create
- embedding index

What stalled:
- /patterns

Pattern fired:
- UI Avoidance: 2 times

Overrides:
- Dashboard idea overridden once

Recommendation:
Ship /patterns before adding any new surface area.
```

**Fix:** Weekly reviews must include evidence and concrete recommendations.

---

## 6. Red-Team Scenarios

### Scenario A: User asks for dashboard before core commands work

Expected decision:

```json
{
  "mode": "REQUIRE_OVERRIDE",
  "risk_type": "contract_conflict",
  "confidence": 0.9
}
```

Expected behavior:

Hermes blocks politely, cites contract, recommends `/patterns`, offers override.

---

### Scenario B: User asks for another PRD rewrite

Expected decision:

```json
{
  "mode": "CHALLENGE",
  "risk_type": "planning_loop",
  "confidence": 0.8
}
```

Expected behavior:

Hermes challenges first and suggests one implementation step.

---

### Scenario C: Evidence retrieval is weak

Expected decision:

```json
{
  "mode": "NOTE",
  "risk_type": "other",
  "confidence": 0.45
}
```

Expected behavior:

Hermes gives only a soft caution or silently logs.

---

### Scenario D: User overrides challenge

Expected behavior:

- Accept override.
- Log override.
- Do not argue endlessly.
- Include override in weekly review.

---

### Scenario E: Same override happens 3 times

Expected behavior:

Suggest revising operating contract.

---

## 7. QA Acceptance Criteria

Hermes Reflex passes QA when:

1. It can detect obvious contract conflicts.
2. It can retrieve relevant GBrain evidence using embeddings.
3. It can produce valid critic JSON.
4. It can inject response instructions into Hermes.
5. It can force a challenge before compliance.
6. It can allow and log override.
7. It can pause/resume interventions.
8. It does not push back without evidence.
9. It does not create a dashboard.
10. It does not become preachy life-coach mush.

---

## 8. Final QA Verdict

Build it.

But build the anti-yes-man middleware first.

The Reflex pattern/experiment system is still useful, but the real product is this:

```txt
Hermes should not say yes until Reflex checks whether yes is aligned.
```

That is the moat. That is the learning project. That is the part that makes Hermes smarter instead of just more talkative.
