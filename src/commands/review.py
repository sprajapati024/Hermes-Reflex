"""Reflex review command.

Triggered by /review. Generates a weekly summary from the past week's
Reflex data: decisions, signals, overrides, experiments.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from ..gbrain.paths import (
    get_decisions_root,
    get_signals_root,
    get_overrides_root,
    get_experiments_root,
    get_reflex_root,
)
from ..gbrain.markdown import read_markdown
from ..gbrain.storage import write_weekly_review, read_active_experiments


def _load_frontmatter_files(glob_pattern: str, root: Path) -> list[dict]:
    """Load frontmatter from files matching a glob pattern under root."""
    results = []
    if not root.exists():
        return results
    # glob recursively
    for f in sorted(root.glob(glob_pattern)):
        try:
            data, _ = read_markdown(f)
            results.append(data)
        except Exception:
            continue
    return results


def _this_week_paths(root: Path, sub: str) -> list[Path]:
    """Return paths from this week's files under root/sub/."""
    week_ago = datetime.now() - timedelta(days=7)
    base = root / sub
    if not base.exists():
        return []
    paths = []
    for f in base.rglob("*.md"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime >= week_ago:
                paths.append(f)
        except Exception:
            continue
    return paths


def run_review() -> str:
    """Generate a weekly review summary.

    Returns a formatted Telegram message with the week's Reflex activity.
    Writes the review to gbrain/reflex/reviews/weekly/.
    """
    root = get_reflex_root()

    # Collect this week's data
    decision_files = _this_week_paths(root, "decisions")
    signal_files = _this_week_paths(root, "signals")
    override_files = _this_week_paths(root, "overrides")

    # Load decisions
    decisions = []
    for f in decision_files:
        try:
            data, _ = read_markdown(f)
            decisions.append(data)
        except Exception:
            continue

    # Load signals
    signals = []
    for f in signal_files:
        try:
            data, _ = read_markdown(f)
            signals.append(data)
        except Exception:
            continue

    # Load overrides
    overrides = []
    for f in override_files:
        try:
            data, _ = read_markdown(f)
            overrides.append(data)
        except Exception:
            continue

    # Count modes
    mode_counts: dict[str, int] = {}
    for d in decisions:
        m = d.get("mode", "ALLOW")
        mode_counts[m] = mode_counts.get(m, 0) + 1

    # Count patterns fired (from signals)
    pattern_counts: dict[str, int] = {}
    for s in signals:
        rt = s.get("risk_type", "unknown")
        pattern_counts[rt] = pattern_counts.get(rt, 0) + 1

    # Active experiments
    experiments = read_active_experiments()

    # Build summary
    lines = ["*Weekly Reflex Review*"]

    if not decisions and not signals and not overrides:
        lines.append("\nNo Reflex activity this week.")
        return "\n".join(lines)

    lines.append(f"\n*Decisions:* {len(decisions)}")
    for mode, count in sorted(mode_counts.items()):
        lines.append(f"  {mode}: {count}")

    if pattern_counts:
        lines.append(f"\n*Patterns Fired:* {len(signals)}")
        for pat, count in sorted(pattern_counts.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"  {pat}: {count}x")

    lines.append(f"\n*Overrides:* {len(overrides)}")
    for o in overrides[:3]:
        rid = o.get("decision_id", "?")
        reason = o.get("reason", "")[:60]
        lines.append(f"  [{rid}] {reason}")

    if experiments:
        lines.append(f"\n*Active Experiments:* {len(experiments)}")
        for e in experiments:
            lines.append(f"  • {e.get('name', '?')}")

    # Write to GBrain
    now = datetime.now()
    year, week_num = now.isocalendar()[:2]

    try:
        write_weekly_review(
            what_shipped=["See decisions log"],
            what_stalled=["See signals log"],
            patterns_fired=pattern_counts,
            interventions_accepted=len(decisions) - len(overrides),
            overrides=[
                {"decision_id": o.get("decision_id", ""), "reason": o.get("reason", "")}
                for o in overrides
            ],
            experiment_results={e.get("name", "?"): e.get("metric", "") for e in experiments},
            next_week_recommendation="Review pattern signals and update experiments.",
            stop_doing="Overriding challenges without logging reason.",
            year=year,
            week=week_num,
            dt=now,
        )
        lines.append(f"\n_Review saved to reviews/weekly/{year}-W{week_num:02d}_")
    except Exception as exc:
        lines.append(f"\n_Warning: could not save review: {exc}_")

    return "\n".join(lines)
