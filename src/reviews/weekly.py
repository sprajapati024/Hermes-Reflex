"""Weekly review generator for Hermes Reflex.

Pulls from checkins, decisions, signals, overrides, and experiments
to write a structured weekly review to GBrain.

Phase 9 of the Hermes Reflex build order.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ..gbrain.paths import (
    get_reflex_root,
    get_checkins_root,
    get_decisions_root,
    get_signals_root,
    get_overrides_root,
    get_experiments_root,
    get_interventions_root,
    get_weekly_review_path,
)
from ..gbrain.markdown import read_markdown
from ..gbrain.frontmatter import parse_frontmatter


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _this_week_files(root: Path, sub: str) -> list[Path]:
    """Return file paths modified within the last 7 days under root/sub/."""
    if not root.exists():
        return []
    base = root / sub
    if not base.exists():
        return []
    cutoff = datetime.now() - timedelta(days=7)
    results = []
    for f in base.rglob("*.md"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime >= cutoff:
                results.append(f)
        except OSError:
            continue
    return sorted(results)


def _frontmatter_from_file(f: Path) -> dict:
    """Read frontmatter from a file, skipping parse errors."""
    try:
        return parse_frontmatter(f.read_text())[0] or {}
    except Exception:
        return {}


# --------------------------------------------------------------------------
# Data collectors
# --------------------------------------------------------------------------


def _load_this_week_checkins(root: Path) -> list[dict]:
    """Load frontmatter from this week's checkin files."""
    files = _this_week_files(root, "checkins")
    results = []
    for f in files:
        data = _frontmatter_from_file(f)
        if data:
            data["_path"] = str(f)
            results.append(data)
    return results


def _load_this_week_decisions(root: Path) -> list[dict]:
    files = _this_week_files(root, "decisions")
    results = []
    for f in files:
        data = _frontmatter_from_file(f)
        if data:
            results.append(data)
    return results


def _load_this_week_overrides(root: Path) -> list[dict]:
    files = _this_week_files(root, "overrides")
    results = []
    for f in files:
        data = _frontmatter_from_file(f)
        if data:
            results.append(data)
    return results


def _load_this_week_interventions(root: Path) -> list[dict]:
    files = _this_week_files(root, "interventions")
    results = []
    for f in files:
        data = _frontmatter_from_file(f)
        if data:
            results.append(data)
    return results


def _load_active_experiments(root: Path) -> list[dict]:
    """Load frontmatter from active experiment files."""
    active_dir = root / "experiments" / "active"
    if not active_dir.exists():
        return []
    results = []
    for f in active_dir.glob("*.md"):
        data = _frontmatter_from_file(f)
        if data:
            data["_path"] = str(f)
            results.append(data)
    return results


def _load_this_week_signals(root: Path) -> list[dict]:
    """Load signals from this week for pattern analysis."""
    files = _this_week_files(root, "signals")
    results = []
    for f in files:
        data = _frontmatter_from_file(f)
        if data:
            results.append(data)
    return results


# --------------------------------------------------------------------------
# Extractors
# --------------------------------------------------------------------------


def _extract_shipped_from_checkins(checkins: list[dict]) -> list[str]:
    """Pull what_shipped from checkin frontmatter."""
    shipped = []
    for c in checkins:
        val = c.get("what_shipped") or c.get("what-shipped", "")
        if val and isinstance(val, str) and val.strip():
            shipped.append(val.strip())
    return shipped


def _extract_stalled_from_checkins(checkins: list[dict]) -> list[str]:
    """Pull what_got_avoided from checkin frontmatter."""
    stalled = []
    for c in checkins:
        val = c.get("what_got_avoided") or c.get("what-got-avoided", "")
        if val and isinstance(val, str) and val.strip():
            stalled.append(val.strip())
    return stalled


def _count_modes(decisions: list[dict]) -> dict[str, int]:
    """Count decision modes."""
    counts: dict[str, int] = {}
    for d in decisions:
        m = d.get("mode", "ALLOW")
        counts[m] = counts.get(m, 0) + 1
    return counts


def _count_patterns_fired(signals: list[dict]) -> dict[str, int]:
    """Count signals by risk_type (pattern)."""
    counts: dict[str, int] = {}
    for s in signals:
        rt = s.get("risk_type") or s.get("signal_type", "unknown")
        counts[rt] = counts.get(rt, 0) + 1
    return counts


# --------------------------------------------------------------------------
# Experiment evaluation
# --------------------------------------------------------------------------


def _evaluate_experiments(
    experiments: list[dict],
    interventions: list[dict],
) -> dict[str, str]:
    """Return {experiment_name: evaluation} for active experiments.

    Evaluation logic:
      - if end_date is in the past → "completed"
      - if has interventions_accepted > 0 → "interventions used, monitor"
      - if no signals fired for the risk type → "no activity"
      - else → "running"
    """
    results: dict[str, str] = {}
    now = datetime.now()
    for e in experiments:
        name = e.get("name", "?")
        end_date_str = e.get("end_date")
        experiment_id = e.get("id", "")

        # Check for end date
        if end_date_str:
            try:
                end = datetime.fromisoformat(end_date_str)
                if end <= now:
                    results[name] = "completed (end date reached)"
                    continue
            except ValueError:
                pass

        # Check for related interventions
        related = [
            i for i in interventions
            if i.get("risk_type", "") == experiment_id
               or i.get("risk_type", "") in experiment_id
        ]
        if related:
            results[name] = f"interventions used ({len(related)} logged)"

        # Check for fired signals
        # Use the experiment_id or name to infer risk type
        signals_root = get_reflex_root() / "signals"
        if signals_root.exists():
            fired = list(signals_root.rglob(f"*{experiment_id}*.md"))
            if fired:
                results[name] = "signals fired during experiment"

        results.setdefault(name, "running")
    return results


# --------------------------------------------------------------------------
# Recommendation engine
# --------------------------------------------------------------------------


def _generate_next_week_recommendation(
    experiments: list[dict],
    decisions: list[dict],
    signals: list[dict],
    overrides: list[dict],
) -> str:
    """Generate one concrete next-week recommendation."""
    # If there are active experiments, recommend evaluating them
    if experiments:
        names = [e.get("name", "?") for e in experiments]
        if len(names) == 1:
            return f"Evaluate '{names[0]}'. Has it passed its success criteria?"
        return f"Running {len(experiments)} experiments: {', '.join(names[:2])}"

    # If there were many overrides, recommend being more skeptical
    if len(overrides) >= 2:
        return "High override count this week. Consider whether the reflex rules need tightening."

    # If no decisions were non-ALLOW, reflex may not be firing enough
    non_allow = [d for d in decisions if d.get("mode", "ALLOW") != "ALLOW"]
    if not non_allow and len(decisions) > 3:
        return "Reflex fired often but no challenges. Check that rules are catching real risks."

    return "Continue current project. Ship before starting anything new."


def _generate_stop_doing(
    overrides: list[dict],
    stalled: list[str],
    signals: list[dict],
) -> str:
    """Generate one 'stop doing' from evidence."""
    if len(overrides) >= 2:
        return "Overriding challenges without a strong reason. Each override weakens the reflex."

    if len(stalled) >= 2:
        return "Same items staying stalled across check-ins. Either remove them or actually do them."

    # Look for repeated risk types in signals
    pattern_counts = _count_patterns_fired(signals)
    if pattern_counts:
        top = max(pattern_counts.items(), key=lambda x: x[1])
        if top[1] >= 3:
            return f"'{top[0]}' firing repeatedly. Build a proper intervention for it."

    return "Starting planning sessions without a concrete next step."


# --------------------------------------------------------------------------
# Section builder
# --------------------------------------------------------------------------


def _build_what_shipped_section(shipped: list[str]) -> str:
    if not shipped:
        return "## What Shipped\nNothing recorded as shipped this week.\n"
    lines = ["## What Shipped"]
    seen: set[str] = set()
    for s in shipped:
        stripped = s.strip()
        if stripped and stripped.lower() not in seen:
            lines.append(f"- {stripped}")
            seen.add(stripped.lower())
    return "\n".join(lines) + "\n"


def _build_what_stalled_section(stalled: list[str]) -> str:
    if not stalled:
        return "## What Stalled\nNothing recorded as stalled this week.\n"
    lines = ["## What Stalled"]
    seen: set[str] = set()
    for s in stalled:
        stripped = s.strip()
        if stripped and stripped.lower() not in seen:
            lines.append(f"- {stripped}")
            seen.add(stripped.lower())
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Main generator
# --------------------------------------------------------------------------


def generate_weekly_review(dt: Optional[datetime] = None) -> dict:
    """Generate the weekly review data dict.

    Returns a dict with:
      - path: Path the review was written to
      - message: Telegram-formatted summary string
      - sections: raw structured data

    Writes the review markdown file to GBrain.
    """
    if dt is None:
        dt = datetime.now()

    root = get_reflex_root()
    year, week_num = dt.isocalendar()[:2]

    # Load data
    checkins = _load_this_week_checkins(root)
    decisions = _load_this_week_decisions(root)
    signals = _load_this_week_signals(root)
    overrides = _load_this_week_overrides(root)
    interventions = _load_this_week_interventions(root)
    experiments = _load_active_experiments(root)

    # Extract structured content
    shipped = _extract_shipped_from_checkins(checkins)
    stalled = _extract_stalled_from_checkins(checkins)

    mode_counts = _count_modes(decisions)
    pattern_counts = _count_patterns_fired(signals)
    experiment_evals = _evaluate_experiments(experiments, interventions)

    interventions_accepted = len(interventions)
    total_decisions = len(decisions)

    # Build sections
    what_shipped_text = _build_what_shipped_section(shipped)
    what_stalled_text = _build_what_stalled_section(stalled)

    patterns_fired_lines = ["## Patterns Fired"]
    if pattern_counts:
        for pat, count in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            patterns_fired_lines.append(f"- {pat}: {count}x")
    else:
        patterns_fired_lines.append("No patterns fired this week.")
    patterns_fired_text = "\n".join(patterns_fired_lines) + "\n"

    interventions_text = (
        f"## Interventions Accepted\n"
        f"{interventions_accepted} of {total_decisions} decisions triggered interventions.\n"
    )

    overrides_lines = ["## Overrides Logged"]
    if overrides:
        for o in overrides:
            rid = o.get("decision_id", "?")
            reason = o.get("reason", "")[:80]
            overrides_lines.append(f"- [{rid}] {reason}")
    else:
        overrides_lines.append("No overrides this week.")
    overrides_text = "\n".join(overrides_lines) + "\n"

    experiment_lines = ["## Experiment Status"]
    if experiment_evals:
        for name, eval_str in experiment_evals.items():
            experiment_lines.append(f"- **{name}**: {eval_str}")
    else:
        experiment_lines.append("No active experiments.")
    experiments_text = "\n".join(experiment_lines) + "\n"

    next_recommendation = _generate_next_week_recommendation(
        experiments, decisions, signals, overrides
    )
    stop_doing = _generate_stop_doing(overrides, stalled, signals)

    next_week_text = (
        f"## Next Week Recommendation\n{next_recommendation}\n"
    )
    stop_text = f"## Stop Doing\n{stop_doing}\n"

    # Assemble body
    body_parts = [
        what_shipped_text,
        what_stalled_text,
        patterns_fired_text,
        interventions_text,
        overrides_text,
        experiments_text,
        next_week_text,
        stop_text,
    ]
    body = "\n".join(body_parts)

    # Frontmatter data
    data = {
        "id": f"review_{year}-W{week_num:02d}",
        "type": "review",
        "review_type": "weekly",
        "year": year,
        "week": week_num,
        "patterns_fired": pattern_counts,
        "mode_counts": mode_counts,
        "interventions_accepted": interventions_accepted,
        "total_decisions": total_decisions,
        "overrides_count": len(overrides),
        "experiments": [e.get("name", "?") for e in experiments],
        "created_at": dt.isoformat(),
    }

    # Write markdown
    review_path = get_weekly_review_path(year, week_num)
    review_path.parent.mkdir(parents=True, exist_ok=True)

    # Use write_markdown via storage import
    from ..gbrain.markdown import write_markdown
    write_markdown(review_path, body, data)

    # Build Telegram message
    msg_lines = [f"*Weekly Reflex Review — {year}-W{week_num:02d}*"]

    if shipped:
        msg_lines.append("\n*What Shipped:*")
        for s in shipped[:5]:
            msg_lines.append(f"  • {s}")
    elif decisions:
        msg_lines.append("\n*What Shipped:* (see decisions log)")

    if stalled:
        msg_lines.append("\n*What Stalled:*")
        for s in stalled[:5]:
            msg_lines.append(f"  • {s}")

    if pattern_counts:
        msg_lines.append("\n*Patterns Fired:*")
        for pat, count in sorted(pattern_counts.items(), key=lambda x: -x[1])[:5]:
            msg_lines.append(f"  {pat}: {count}x")

    if mode_counts:
        msg_lines.append("\n*Decision Modes:*")
        for mode, count in sorted(mode_counts.items()):
            msg_lines.append(f"  {mode}: {count}")

    msg_lines.append(f"\n*Interventions Accepted:* {interventions_accepted}/{total_decisions}")
    msg_lines.append(f"*Overrides:* {len(overrides)}")

    if experiment_evals:
        msg_lines.append("\n*Experiments:*")
        for name, eval_str in experiment_evals.items():
            msg_lines.append(f"  • {name}: {eval_str}")

    msg_lines.append(f"\n*Next Week:* {next_recommendation}")
    msg_lines.append(f"*Stop Doing:* {stop_doing}")
    msg_lines.append(f"\n_Review saved._")

    message = "\n".join(msg_lines)

    return {
        "path": str(review_path),
        "message": message,
        "sections": {
            "what_shipped": shipped,
            "what_stalled": stalled,
            "patterns_fired": pattern_counts,
            "mode_counts": mode_counts,
            "interventions_accepted": interventions_accepted,
            "total_decisions": total_decisions,
            "overrides_count": len(overrides),
            "experiment_results": experiment_evals,
            "next_week_recommendation": next_recommendation,
            "stop_doing": stop_doing,
        },
    }
