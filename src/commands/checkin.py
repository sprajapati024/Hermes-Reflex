"""Reflex check-in command.

Triggered by /checkin. Runs an interactive 6-question check-in and writes
the result to gbrain/reflex/checkins/YYYY/MM/YYYY-MM-DD.md.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from ..gbrain.storage import write_checkin


def run_checkin(
    *,
    energy: Optional[int] = None,
    available_time: Optional[str] = None,
    biggest_friction: Optional[str] = None,
    main_focus: Optional[str] = None,
    what_shipped: Optional[str] = None,
    what_got_avoided: Optional[str] = None,
    notes: Optional[str] = None,
    dt: Optional[datetime] = None,
) -> str:
    """Run a check-in with the provided answers.

    Writes to gbrain/reflex/checkins/YYYY/MM/YYYY-MM-DD.md.

    Returns a one-line summary suitable for Telegram.
    """
    path = write_checkin(
        energy=energy,
        available_time=available_time,
        biggest_friction=biggest_friction,
        main_focus=main_focus,
        what_shipped=what_shipped,
        what_got_avoided=what_got_avoided,
        notes=notes,
        dt=dt,
    )
    return f"✅ Check-in saved to {path.name}"


# Questions for interactive check-in flow
CHECKIN_QUESTIONS = [
    {
        "key": "energy",
        "prompt": "⚡ Energy 1-10?",
        "validator": lambda v: v is None or (v.isdigit() and 1 <= int(v) <= 10),
    },
    {
        "key": "available_time",
        "prompt": "⏱️ Available time today? (e.g. 2hrs, half day, full day)",
        "validator": lambda v: True,  # free text
    },
    {
        "key": "biggest_friction",
        "prompt": "🔴 Biggest friction right now?",
        "validator": lambda v: True,
    },
    {
        "key": "main_focus",
        "prompt": "🎯 Main focus for today?",
        "validator": lambda v: True,
    },
    {
        "key": "what_shipped",
        "prompt": "🚀 What shipped recently?",
        "validator": lambda v: True,
    },
    {
        "key": "what_got_avoided",
        "prompt": "🛑 What got avoided?",
        "validator": lambda v: True,
    },
]


def format_checkin_summary(
    *,
    energy: Optional[int] = None,
    available_time: Optional[str] = None,
    biggest_friction: Optional[str] = None,
    main_focus: Optional[str] = None,
    what_shipped: Optional[str] = None,
    what_got_avoided: Optional[str] = None,
) -> str:
    """Format a human-readable check-in summary for Telegram."""
    lines = ["*Check-in Summary*"]
    if energy is not None:
        lines.append(f"⚡ Energy: {energy}/10")
    if available_time:
        lines.append(f"⏱️ Time: {available_time}")
    if main_focus:
        lines.append(f"🎯 Focus: {main_focus}")
    if what_shipped:
        lines.append(f"🚀 Shipped: {what_shipped}")
    if what_got_avoided:
        lines.append(f"🛑 Avoided: {what_got_avoided}")
    if biggest_friction:
        lines.append(f"🔴 Friction: {biggest_friction}")
    return "\n".join(lines)
