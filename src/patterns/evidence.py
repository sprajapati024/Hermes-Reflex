"""Pattern evidence tracking for Hermes Reflex.

Tracks related signals for a pattern and determines when promotion
thresholds are met.

Promotion rules (per IMPLEMENTATION_PLAN):
  candidate → watching:  2+ related signals in 14 days
  watching  → active:    3+ related signals + one useful intervention available
  active    → retired:   No firing for 30 days or user retires it
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ..gbrain.paths import get_signals_root, get_patterns_root, get_interventions_root
from ..gbrain.markdown import read_markdown


# Promotion thresholds
CANDIDATE_TO_WATCHING_SIGNALS = 2
CANDIDATE_WINDOW_DAYS = 14
WATCHING_TO_ACTIVE_SIGNALS = 3
ACTIVE_FIRELESS_DAYS = 30


def _get_signal_files_in_window(status_dir: Path, window_days: int) -> list[Path]:
    """Return all signal files modified within the window."""
    if not status_dir.exists():
        return []
    cutoff = datetime.now() - timedelta(days=window_days)
    files = []
    for f in status_dir.rglob("*.md"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime >= cutoff:
                files.append(f)
        except OSError:
            continue
    return files


def _load_signals_for_pattern(pattern_id: str, window_days: int) -> list[dict]:
    """Load signals related to this pattern within the window."""
    signals_root = get_signals_root()
    if not signals_root.exists():
        return []
    cutoff = datetime.now() - timedelta(days=window_days)
    results = []
    for f in signals_root.rglob("*.md"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime >= cutoff:
                data, _ = read_markdown(f)
                if data.get("risk_type") == pattern_id or pattern_id in data.get("risk_type", ""):
                    results.append(data)
        except Exception:
            continue
    return results


def count_signals_for_pattern(pattern_id: str, status: str) -> int:
    """Count signals for a pattern in its current status dir (all-time for current life)."""
    patterns_root = get_patterns_root()
    status_dir = patterns_root / status
    count = 0
    for f in (status_dir / pattern_id).glob("*.md") if (status_dir / pattern_id).exists() else []:
        count += 1
    return count


def count_signals_in_window(pattern_id: str, window_days: int = CANDIDATE_WINDOW_DAYS) -> int:
    """Count signals related to this pattern in the last N days."""
    return len(_load_signals_for_pattern(pattern_id, window_days))


def has_useful_intervention(pattern_id: str) -> bool:
    """Return True if there's at least one accepted intervention for this pattern."""
    interventions_root = get_interventions_root()
    if not interventions_root.exists():
        return False
    for f in interventions_root.rglob("*.md"):
        try:
            data, _ = read_markdown(f)
            if data.get("risk_type") == pattern_id:
                return True
        except Exception:
            continue
    return False


def get_days_since_last_firing(pattern_id: str) -> Optional[int]:
    """Return days since last signal for this pattern. None if never fired.

    Only looks at actual signal files under get_signals_root(), NOT pattern files.
    """
    signals_root = get_signals_root()
    if not signals_root.exists():
        return None
    all_mtimes: list[datetime] = []
    for f in signals_root.rglob("*.md"):
        try:
            data, _ = read_markdown(f)
            if data.get("risk_type") == pattern_id:
                all_mtimes.append(datetime.fromtimestamp(f.stat().st_mtime))
        except Exception:
            continue
    if not all_mtimes:
        return None
    last_firing = max(all_mtimes)
    return (datetime.now() - last_firing).days


def get_evidence_summary(pattern_id: str) -> dict:
    """Return a summary of evidence for a pattern."""
    window_signals = count_signals_in_window(pattern_id, CANDIDATE_WINDOW_DAYS)

    # Count all actual signal files for this pattern (not pattern files)
    signals_root = get_signals_root()
    total_signals = 0
    if signals_root.exists():
        for f in signals_root.rglob("*.md"):
            try:
                data, _ = read_markdown(f)
                if data.get("risk_type") == pattern_id:
                    total_signals += 1
            except Exception:
                continue

    interventions = has_useful_intervention(pattern_id)
    days_since = get_days_since_last_firing(pattern_id)

    return {
        "signals_in_window": window_signals,
        "total_signals": total_signals,
        "has_intervention": interventions,
        "days_since_firing": days_since,
        "candidate_threshold_met": window_signals >= CANDIDATE_TO_WATCHING_SIGNALS,
        "watching_threshold_met": (
            window_signals >= WATCHING_TO_ACTIVE_SIGNALS and interventions
        ),
        "retire_threshold_met": (
            days_since is not None and days_since >= ACTIVE_FIRELESS_DAYS
        ),
    }
