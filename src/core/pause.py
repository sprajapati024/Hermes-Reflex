"""Pause / resume state for Hermes Reflex.

Tracks whether proactive Reflex interventions are paused and for how long.
State is stored in a simple JSON file under the reflex root — no database needed.

Pause levels:
  - today:  interventions paused until midnight UTC
  - week:   interventions paused until end of week (Sunday UTC)
  - off:    fully resumed (interventions enabled)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..gbrain.paths import get_reflex_root


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _get_pause_file() -> Path:
    return get_reflex_root() / "pause_state.json"


# ---------------------------------------------------------------------------
# State shape
# ---------------------------------------------------------------------------

_PAUSE_LEVELS = {"today", "week", "off"}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_pause_state() -> dict:
    """Return the current pause state.

    Returns:
        dict with keys: paused (bool), level (str), until_utc (str or None)
    """
    path = _get_pause_file()
    if not path.exists():
        return {"paused": False, "level": "off", "until_utc": None}

    try:
        with open(path) as f:
            state = json.load(f)
    except Exception:
        return {"paused": False, "level": "off", "until_utc": None}

    # Check expiry
    until_utc = state.get("until_utc")
    if until_utc:
        try:
            until_dt = datetime.fromisoformat(until_utc)
            if _now_utc() >= until_dt:
                # Expired — delete file and return off state
                path.unlink(missing_ok=True)
                return {"paused": False, "level": "off", "until_utc": None}
        except ValueError:
            # Bad timestamp — treat as expired
            path.unlink(missing_ok=True)
            return {"paused": False, "level": "off", "until_utc": None}

    return state


def is_paused() -> bool:
    """Return True if proactive interventions are currently paused."""
    return get_pause_state().get("paused", False)


def pause(level: str = "today") -> dict:
    """Pause Reflex interventions.

    Args:
        level: One of "today", "week", or "off" (which resumes).

    Returns:
        The new pause state.
    """
    if level == "off":
        return resume()

    if level not in _PAUSE_LEVELS:
        raise ValueError(f"Invalid pause level {level!r}. Must be one of: {_PAUSE_LEVELS}")

    now = _now_utc()

    if level == "today":
        # Until end of today UTC
        until_dt = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif level == "week":
        # Until end of next Sunday UTC
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        until_dt = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        from datetime import timedelta
        until_dt += timedelta(days=days_until_sunday)
    else:
        until_dt = now  # shouldn't happen

    state = {
        "paused": True,
        "level": level,
        "until_utc": until_dt.isoformat(),
        "paused_at_utc": now.isoformat(),
    }

    path = _get_pause_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)

    return state


def resume() -> dict:
    """Resume Reflex interventions (clear pause state)."""
    path = _get_pause_file()
    path.unlink(missing_ok=True)
    return {"paused": False, "level": "off", "until_utc": None}
