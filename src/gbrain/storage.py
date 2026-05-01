"""GBrain/Reflex storage layer — high-level CRUD operations.

All Reflex data lives as markdown files with YAML frontmatter under the GBrain root.
Date-based subdirs (YYYY/MM/) are created automatically.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .paths import (
    get_reflex_root,
    get_current_contract_path,
    get_checkin_path,
    get_signal_path,
    get_decision_path,
    get_experiment_path,
    get_intervention_path,
    get_override_path,
    get_weekly_review_path,
    get_pattern_path,
    get_skillify_candidate_path,
    get_patterns_root,
    get_experiments_root,
    ensure_dir,
)
from .markdown import read_markdown, write_markdown, file_exists


# ---------------------------------------------------------------------------
# Structure bootstrap
# ---------------------------------------------------------------------------

def ensure_reflex_structure() -> Path:
    """Create the full GBrain/Reflex directory tree if missing.

    Returns the reflex root path.
    """
    root = get_reflex_root()
    for sub in (
        "contracts",
        "checkins",
        "signals",
        "decisions",
        "patterns/candidate",
        "patterns/watching",
        "patterns/active",
        "patterns/retired",
        "experiments/planned",
        "experiments/active",
        "experiments/completed",
        "experiments/abandoned",
        "interventions",
        "overrides",
        "reviews/weekly",
        "reviews/monthly",
        "skillify-candidates",
        "embeddings",
    ):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


# ---------------------------------------------------------------------------
# Check-ins
# ---------------------------------------------------------------------------

def write_checkin(
    *,
    energy: Optional[int] = None,
    available_time: Optional[str] = None,
    biggest_friction: Optional[str] = None,
    main_focus: Optional[str] = None,
    what_shipped: Optional[str] = None,
    what_got_avoided: Optional[str] = None,
    notes: Optional[str] = None,
    dt: Optional[datetime] = None,
) -> Path:
    """Write a daily check-in file."""
    body = ""
    data = {
        "id": f"checkin_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "type": "checkin",
    }
    for key, val in [
        ("energy", energy),
        ("available_time", available_time),
        ("biggest_friction", biggest_friction),
        ("main_focus", main_focus),
        ("what_shipped", what_shipped),
        ("what_got_avoided", what_got_avoided),
        ("notes", notes),
    ]:
        if val is not None:
            body += f"## {key.replace('_', ' ').title()}\n{val}\n\n"
            data[key] = val

    path = get_checkin_path(dt)
    write_markdown(path, body.strip(), data)
    return path


def read_checkin(dt: Optional[datetime] = None) -> tuple[dict[str, Any], str]:
    """Read the checkin file for a given date (defaults to today)."""
    path = get_checkin_path(dt)
    return read_markdown(path)


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

def write_signal(
    *,
    signal_type: str,
    source: str = "telegram",
    project: Optional[str] = None,
    confidence: float,
    severity: str,
    evidence: str,
    risk_type: Optional[str] = None,
    decision_id: Optional[str] = None,
    dt: Optional[datetime] = None,
) -> Path:
    """Write a signal file."""
    if dt is None:
        dt = datetime.now()
    data = {
        "id": f"signal_{dt.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}",
        "type": "signal",
        "signal_type": signal_type,
        "source": source,
        "project": project,
        "confidence": confidence,
        "severity": severity,
        "risk_type": risk_type,
        "evidence": evidence,
        "decision_id": decision_id,
        "created_at": dt.isoformat(),
    }
    body = f"## Evidence\n{evidence}\n"
    path = get_signal_path(dt)
    write_markdown(path, body, data)
    return path


# ---------------------------------------------------------------------------
# Critic Decisions
# ---------------------------------------------------------------------------

def write_decision(
    *,
    mode: str,
    risk_type: str,
    confidence: float,
    severity: str,
    evidence_ids: list[str],
    reason: str,
    recommended_action: str,
    allow_override: bool = True,
    user_message: Optional[str] = None,
    rule_result: Optional[dict[str, Any]] = None,
    contract_conflict: Optional[dict[str, Any]] = None,
    retrieved_evidence: Optional[list[dict[str, Any]]] = None,
    dt: Optional[datetime] = None,
) -> Path:
    """Write a critic decision file."""
    if dt is None:
        dt = datetime.now()
    data = {
        "id": f"decision_{dt.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}",
        "type": "decision",
        "mode": mode,
        "risk_type": risk_type,
        "confidence": confidence,
        "severity": severity,
        "evidence_ids": evidence_ids,
        "reason": reason,
        "recommended_action": recommended_action,
        "allow_override": allow_override,
        "created_at": dt.isoformat(),
    }
    body = f"## Reason\n{reason}\n\n## Recommended Action\n{recommended_action}\n"
    path = get_decision_path(dt)
    write_markdown(path, body, data)
    return path


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------

def write_experiment(
    *,
    name: str,
    hypothesis: str,
    rules: list[str],
    metric: str,
    success_criteria: str,
    status: str = "active",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    experiment_id: Optional[str] = None,
) -> Path:
    """Write an experiment file."""
    if experiment_id is None:
        experiment_id = name.lower().replace(" ", "-").replace("_", "-")
    if start_date is None:
        start_date = datetime.now()
    data = {
        "id": experiment_id,
        "type": "experiment",
        "name": name,
        "status": status,
        "hypothesis": hypothesis,
        "metric": metric,
        "success_criteria": success_criteria,
        "start_date": start_date.date().isoformat() if start_date else None,
        "end_date": end_date.date().isoformat() if end_date else None,
        "created_at": datetime.now().isoformat(),
    }
    body = f"## Hypothesis\n{hypothesis}\n\n## Rules\n" + "\n".join(f"- {r}" for r in rules) + f"\n\n## Metric\n{metric}\n\n## Success Criteria\n{success_criteria}\n"
    path = get_experiment_path(experiment_id, status)
    write_markdown(path, body, data)
    return path


def read_experiment(experiment_id: str, status: str = "active") -> tuple[dict[str, Any], str]:
    """Read an experiment file."""
    path = get_experiment_path(experiment_id, status)
    return read_markdown(path)


def read_active_experiments() -> list[dict[str, Any]]:
    """Return frontmatter dicts for all active experiments."""
    root = get_experiments_root() / "active"
    results = []
    if not root.exists():
        return results
    for f in root.glob("*.md"):
        data, _ = read_markdown(f)
        results.append(data)
    return results


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

def write_pattern(
    *,
    pattern_id: str,
    name: str,
    status: str,
    confidence: float,
    evidence_count: int,
    intervention: str,
    description: Optional[str] = None,
    risk_type: Optional[str] = None,
    last_seen: Optional[str] = None,
) -> Path:
    """Write a pattern file."""
    data = {
        "id": pattern_id,
        "type": "pattern",
        "name": name,
        "status": status,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "intervention": intervention,
        "risk_type": risk_type,
        "last_seen": last_seen or datetime.now().date().isoformat(),
        "created_at": datetime.now().isoformat(),
    }
    body = f"## Intervention\n{intervention}\n"
    if description:
        body = f"## Description\n{description}\n\n" + body
    path = get_pattern_path(pattern_id, status)
    write_markdown(path, body, data)
    return path


def read_pattern(pattern_id: str, status: str = "active") -> tuple[dict[str, Any], str]:
    path = get_pattern_path(pattern_id, status)
    return read_markdown(path)


def read_active_patterns() -> list[dict[str, Any]]:
    """Return frontmatter dicts for all active patterns."""
    root = get_patterns_root() / "active"
    results = []
    if not root.exists():
        return results
    for f in root.glob("*.md"):
        data, _ = read_markdown(f)
        results.append(data)
    return results


# ---------------------------------------------------------------------------
# Interventions
# ---------------------------------------------------------------------------

def write_intervention(
    *,
    decision_id: str,
    mode: str,
    risk_type: str,
    recommended_action: str,
    response_text: Optional[str] = None,
    dt: Optional[datetime] = None,
) -> Path:
    """Write an intervention file."""
    if dt is None:
        dt = datetime.now()
    data = {
        "id": f"intervention_{dt.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}",
        "type": "intervention",
        "decision_id": decision_id,
        "mode": mode,
        "risk_type": risk_type,
        "recommended_action": recommended_action,
        "created_at": dt.isoformat(),
    }
    body = f"## Recommended Action\n{recommended_action}\n"
    if response_text:
        body += f"\n## Response Text\n{response_text}\n"
    path = get_intervention_path(dt)
    write_markdown(path, body, data)
    return path


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------

def write_override(
    *,
    decision_id: str,
    reason: str,
    original_mode: str,
    dt: Optional[datetime] = None,
) -> Path:
    """Write an override file."""
    if dt is None:
        dt = datetime.now()
    data = {
        "id": f"override_{dt.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}",
        "type": "override",
        "decision_id": decision_id,
        "original_mode": original_mode,
        "reason": reason,
        "created_at": dt.isoformat(),
    }
    body = f"## Reason\n{reason}\n"
    path = get_override_path(dt)
    write_markdown(path, body, data)
    return path


# ---------------------------------------------------------------------------
# Weekly Reviews
# ---------------------------------------------------------------------------

def write_weekly_review(
    *,
    what_shipped: list[str],
    what_stalled: list[str],
    patterns_fired: dict[str, int],
    interventions_accepted: int,
    overrides: list[dict[str, str]],
    experiment_results: dict[str, str],
    next_week_recommendation: str,
    stop_doing: str,
    year: Optional[int] = None,
    week: Optional[int] = None,
    dt: Optional[datetime] = None,
) -> Path:
    """Write a weekly review file."""
    if dt is None:
        dt = datetime.now()
    if year is None:
        year = dt.isocalendar()[0]
    if week is None:
        week = dt.isocalendar()[1]

    data = {
        "id": f"review_{year}-W{week:02d}",
        "type": "review",
        "review_type": "weekly",
        "year": year,
        "week": week,
        "patterns_fired": patterns_fired,
        "interventions_accepted": interventions_accepted,
        "created_at": dt.isoformat(),
    }
    body = "## What Shipped\n" + "\n".join(f"- {s}" for s in what_shipped)
    body += "\n\n## What Stalled\n" + "\n".join(f"- {s}" for s in what_stalled)
    body += "\n\n## Patterns Fired\n" + "\n".join(f"- {k}: {v}x" for k, v in patterns_fired.items())
    body += f"\n\n## Interventions Accepted\n{interventions_accepted}\n"
    body += "\n## Overrides\n" + "\n".join(f"- [{o.get('decision_id','?')}] {o.get('reason','')}" for o in overrides)
    body += "\n\n## Experiment Results\n" + "\n".join(f"- **{k}**: {v}" for k, v in experiment_results.items())
    body += f"\n\n## Next Week Recommendation\n{next_week_recommendation}\n"
    body += f"\n## Stop Doing\n{stop_doing}\n"

    path = get_weekly_review_path(year, week)
    write_markdown(path, body, data)
    return path


# ---------------------------------------------------------------------------
# Operating Contract
# ---------------------------------------------------------------------------

def write_operating_contract(
    *,
    active_goal: str,
    constraints: list[str],
    reflex_authority: str,
    override_policy: str,
) -> Path:
    """Write the current operating contract."""
    data = {
        "id": "current-operating-contract",
        "status": "active",
        "type": "contract",
        "active_goal": active_goal,
        "constraints": constraints,
        "reflex_authority": reflex_authority,
        "override_policy": override_policy,
    }
    body = "# Current Operating Contract\n\n"
    body += f"## Active Goal\n{active_goal}\n\n"
    body += "## Constraints\n" + "\n".join(f"- {c}" for c in constraints) + "\n\n"
    body += f"## Reflex Authority\n{reflex_authority}\n\n"
    body += f"## Override Policy\n{override_policy}\n"

    path = get_current_contract_path()
    write_markdown(path, body, data)
    return path


def read_current_contract() -> tuple[dict[str, Any], str]:
    """Read the current operating contract."""
    path = get_current_contract_path()
    return read_markdown(path)
