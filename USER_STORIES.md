# Hermes Reflex - User Stories and Flows

**Status:** Locked v1 user flows  
**Interface:** Telegram  
**Core behavior:** Anti-yes-man middleware with evidence-backed pushback

---

## 1. Primary User

Shirin uses Hermes through Telegram and GBrain as long-term memory.

He does not want another dashboard. He wants Hermes to stop being an overly agreeable assistant and become an execution-aware partner that can challenge bad loops before they waste time.

---

## 2. Core User Story

As Shirin, I want Hermes to check my request against my goals, active experiments, known patterns, and operating contract before agreeing, so that Hermes helps me execute instead of politely enabling scope creep, planning loops, and fake productivity.

---

## 3. Story: Anti-Yes-Man Challenge

### User Story

As Shirin, I want Hermes to push back when I ask for something that conflicts with my active operating contract.

### Flow

```txt
User:
Maybe we should add a dashboard so I can see patterns visually.

Hermes Reflex internal decision:
mode: REQUIRE_OVERRIDE
risk_type: contract_conflict
confidence: 0.90
evidence:
- current-operating-contract.md: No dashboard
- exp_no_dashboard_build.md: active experiment
recommended_action: Finish /patterns before dashboard work

Hermes:
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

### Acceptance Criteria

- Hermes does not immediately comply.
- Hermes cites contract/evidence.
- Hermes gives one better action.
- Hermes allows override.

---

## 4. Story: Soft Note Instead of Hard Challenge

### User Story

As Shirin, I want Hermes to avoid overreacting when evidence is weak.

### Flow

```txt
User:
Maybe later we can visualize these patterns.

Hermes Reflex internal decision:
mode: NOTE
risk_type: ui_avoidance
confidence: 0.48

Hermes:
Could be useful later. For now, I’d park it until /patterns and /review are stable.

Suggested action:
Add it to backlog, don’t build it yet.
```

### Acceptance Criteria

- Weak evidence does not trigger hard block.
- Hermes gives a light caution.
- Idea can be parked.

---

## 5. Story: Daily Check-In

### User Story

As Shirin, I want to run a quick daily check-in so Hermes Reflex has fresh context for recommendations.

### Flow

```txt
User: /checkin

Hermes: Energy 1-10?
User: 6

Hermes: Available time today?
User: 90 minutes

Hermes: Biggest friction?
User: Too many projects and I keep wanting to redesign things.

Hermes: Main focus?
User: Hermes Reflex

Hermes:
Check-in saved.

Reflex recommendation:
Build /experiment create before touching PRD or UI.
```

### Acceptance Criteria

- Check-in is short.
- Check-in writes to GBrain.
- Hermes returns one useful next action.

---

## 6. Story: Create Experiment

### User Story

As Shirin, I want Hermes to create experiments from recurring problems so I can test whether a behavior change improves execution.

### Flow

```txt
User: /experiment create no dashboard build

Hermes:
Experiment created.

Hypothesis:
If you avoid frontend/dashboard work for 7 days, you will ship the Hermes Reflex core loop faster.

Rules:
1. No dashboard
2. No frontend
3. Telegram commands only
4. GBrain markdown only

Metric:
Working commands shipped.

Success criteria:
4 working commands in 7 days.
```

### Acceptance Criteria

- Experiment has hypothesis, rules, metric, and success criteria.
- Experiment is saved to GBrain.
- Experiment can be used by Reflex critic later.

---

## 7. Story: Reflex Recommendation

### User Story

As Shirin, I want to ask Hermes what to work on and get a recommendation that considers my current experiment, energy, and known patterns.

### Flow

```txt
User: /reflex what should I work on tonight?

Hermes Reflex retrieves:
- latest check-in
- active No Dashboard Build experiment
- Planning Loop pattern
- current operating contract

Hermes:
Best next action:
Build the OpenAI embedding index.

Why:
- It is core to the anti-yes-man layer.
- It supports evidence-backed pushback.
- It does not violate the no-dashboard contract.

Avoid:
- Rewriting the PRD again
- Designing UI
- Adding integrations

45-minute plan:
1. Create embeddings/openai_client.py
2. Add env-based API key loading
3. Embed one contract file
4. Store result in SQLite
```

### Acceptance Criteria

- Recommendation is one action.
- Recommendation references relevant context.
- Recommendation avoids generic advice.

---

## 8. Story: Override

### User Story

As Shirin, I want to override Reflex when I intentionally choose to continue so Hermes remains my tool, not a tiny bureaucrat with a YAML badge.

### Flow

```txt
User: Override. Continue with dashboard idea.

Hermes:
Override logged.
I’ll continue, but this will appear in the weekly review as a No Dashboard Build override.
```

### Acceptance Criteria

- Override is accepted.
- Override is logged.
- Hermes does not argue repeatedly.
- Weekly review includes override.

---

## 9. Story: Pause Reflex

### User Story

As Shirin, I want to pause proactive Reflex interventions when I do not want pushback.

### Flow

```txt
User: /reflex pause today

Hermes:
Reflex proactive interventions paused until tomorrow.
Manual commands still work.
```

### Acceptance Criteria

- Pause works for today/week.
- Manual commands still work.
- Resume command restores interventions.

---

## 10. Story: Pattern Detection

### User Story

As Shirin, I want Hermes to show evidence-backed patterns so I can see what Reflex is using to challenge me.

### Flow

```txt
User: /patterns

Hermes:
Active Pattern: Planning Loop
Confidence: 0.82

Evidence:
- Requested PRD rewrite before implementation
- Revisited architecture before shipping /patterns
- Asked for advanced scope before embedding index was done

Intervention:
One implementation task before more planning.
```

### Acceptance Criteria

- Pattern has confidence.
- Pattern has evidence.
- Pattern has intervention.
- Pattern does not make medical or psychological claims.

---

## 11. Story: Weekly Review

### User Story

As Shirin, I want a weekly review that tells me what shipped, what stalled, what Reflex challenged, and what I overrode.

### Flow

```txt
User: /review

Hermes:
Weekly Reflex Review

What shipped:
- Operating contract
- OpenAI embedding index
- /experiment create

What stalled:
- /patterns command

Patterns fired:
- UI Avoidance: 2 times
- Planning Loop: 1 time

Overrides:
- Dashboard idea overridden once

Experiment result:
No Dashboard Build is still active. You are 2/4 commands shipped.

Next week recommendation:
Ship /patterns before any new feature.

Stop doing:
Expanding architecture before proving middleware.
```

### Acceptance Criteria

- Review is evidence-backed.
- Review includes overrides.
- Review includes one recommendation.
- Review writes to GBrain.

---

## 12. Two-Month Experience

After two months, Hermes Reflex should feel like this:

### Morning

```txt
Hermes:
Morning Reflex Pulse

Best move today:
Finish /patterns confidence scoring.

Why:
- It completes the critic evidence loop.
- It supports weekly reviews.
- It is blocking skillify candidates.

Avoid:
Dashboard idea. Still not time.

Active experiment:
Two-Project Limit

Reply:
1. Start focus block
2. Show steps
3. Override
4. Pause today
```

### Midday

```txt
User:
Maybe we should make Hermes Reflex a full SaaS later.

Hermes:
Reflex note: future product idea parked.

Reason:
This is not blocking v1. Current priority is middleware reliability.

Saved to:
reflex/backlog/future-saas-life-lab.md
```

### Evening

```txt
User: /checkin

Hermes:
Energy?

User: 5

Hermes:
Given low energy, do not start architecture work.
Minimum viable win:
Fix one failing embedding test.
```

### Weekly

```txt
Hermes:
Your override rate dropped from 4 to 1 this week.
UI Avoidance fired once, down from 3.
Planning Loop fired twice.
Recommendation: keep Backend-First Evenings for one more week.
```

This is the desired state: Hermes has evidence-backed instincts and stops behaving like a polite autocomplete servant.

---

## 13. North Star User Experience

The user should feel:

- challenged, not nagged
- supported, not obeyed blindly
- in control, not blocked
- understood through evidence, not vibes
- pushed toward shipping, not more planning

Hermes Reflex should be a loyal skeptic.

Not a coach. Not a therapist. Not a dashboard. Not a productivity cult.

A reflex.
