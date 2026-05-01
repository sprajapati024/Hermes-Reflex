"""Reflex pause / resume command.

Triggered by /reflex pause today, /reflex pause week, /reflex resume.
"""

from __future__ import annotations

from ..core.pause import get_pause_state, pause as pause_reflex, resume as resume_reflex


def run_pause(level: str = "today") -> str:
    """Pause Reflex interventions.

    Args:
        level: "today" (until midnight UTC) or "week" (until Sunday UTC).

    Returns a one-line summary suitable for Telegram.
    """
    if level not in ("today", "week"):
        return "Usage: /reflex pause today  or  /reflex pause week"

    state = pause_reflex(level)
    until = state.get("until_utc", "")
    level_label = state.get("level", level)

    if level == "today":
        return (
            f"🔇 Reflex paused *today*.\\n"
            f"Interventions resume at midnight UTC."
        )
    else:
        return (
            f"🔇 Reflex paused *this week*.\\n"
            f"Resumes Sunday midnight UTC."
        )


def run_resume() -> str:
    """Resume Reflex interventions."""
    state = resume_reflex()
    return "🔊 Reflex resumed. Interventions are back on."


def run_pause_status() -> str:
    """Return current pause state."""
    state = get_pause_state()

    if not state.get("paused"):
        return "🔊 Reflex is *active*. No pause active."

    level = state.get("level", "today")
    until = state.get("until_utc", "?")

    if level == "today":
        return (
            f"🔇 Reflex paused *today*.\\n"
            f"Until: {until}"
        )
    elif level == "week":
        return (
            f"🔇 Reflex paused *this week*.\\n"
            f"Until: {until}"
        )
    else:
        return (
            f"🔇 Reflex paused ({level}).\\n"
            f"Until: {until}"
        )
