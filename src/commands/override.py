"""Reflex override command.

Triggered by /override. Logs that the user chose to override a Reflex
challenge, continuing despite the warning.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..gbrain.storage import write_override


def run_override(
    *,
    decision_id: Optional[str] = None,
    reason: Optional[str] = None,
    original_mode: str = "CHALLENGE",
) -> str:
    """Log an override.

    Args:
        decision_id: The Reflex decision ID being overridden (if any).
        reason: Why the user is overriding.
        original_mode: What mode Reflex had recommended.

    Returns a one-line summary suitable for Telegram.
    """
    if not reason:
        return (
            "Usage: /override <reason>\\n"
            "Example: /override I'm aware of the risk but need to proceed."
        )

    path = write_override(
        decision_id=decision_id or "unknown",
        reason=reason,
        original_mode=original_mode,
        dt=datetime.now(),
    )
    return (
        f"⚠️ Override logged.\\n"
        f"_ID: {decision_id or 'unknown'}_\\n"
        f"Noted: {reason}"
    )


def run_override_status() -> str:
    """Return override count for recent period."""
    from ..gbrain.paths import get_override_path
    from pathlib import Path

    root = get_override_path()
    if not root.exists():
        return "No overrides logged yet."

    overrides = list(root.glob("*.md"))
    if not overrides:
        return "No overrides logged yet."

    # Count this week's overrides
    now = datetime.now()
    week_overrides = [
        f for f in overrides
        if (now - datetime.fromtimestamp(f.stat().st_mtime)).days < 7
    ]

    return (
        f"*Override Stats*\\n"
        f"Total: {len(overrides)}\\n"
        f"This week: {len(week_overrides)}"
    )
