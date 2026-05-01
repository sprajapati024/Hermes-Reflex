"""Reflex review command.

Triggered by /review. Delegates to the Phase 9 weekly review generator so the
Telegram command uses the same evidence-backed review implementation as the
programmatic API.
"""

from __future__ import annotations

from ..reviews.weekly import generate_weekly_review


def run_review() -> str:
    """Generate a weekly review and return the Telegram-ready message."""
    review = generate_weekly_review()
    return review["message"]
