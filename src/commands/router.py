"""Reflex command router.

Receives raw Telegram message text and dispatches to the appropriate command.
Returns a string response suitable for Telegram.

Commands:
  /checkin                    — interactive check-in flow
  /experiment create <name>    — create an experiment
  /experiment list             — list active experiments
  /patterns                    — list active/watching patterns
  /patterns <id>               — detail for a specific pattern
  /reflex <question>           — run Reflex middleware manually
  /review                      — generate weekly review
  /override <reason>           — log an override
  /reflex pause today           — pause interventions today
  /reflex pause week            — pause interventions this week
  /reflex resume                — resume interventions
  /pause                       — check pause status
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from .checkin import run_checkin, format_checkin_summary
from .experiment import run_experiment_create, run_experiment_list
from .patterns import run_patterns_list, run_patterns_detail
from .reflex import run_reflex_query
from .review import run_review
from .override import run_override, run_override_status
from .pause import run_pause, run_resume, run_pause_status


log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Check-in state tracker (session-level)
# --------------------------------------------------------------------------

class CheckinSession:
    """Holds in-progress check-in answers for a user session.

    In production this would be backed by Redis or similar so it survives
    across messages. Here we use a module-level dict keyed by chat_id.
    """

    _sessions: dict[int, dict] = {}

    @classmethod
    def get(cls, chat_id: int) -> dict:
        return cls._sessions.setdefault(chat_id, {})

    @classmethod
    def clear(cls, chat_id: int) -> None:
        cls._sessions.pop(chat_id, None)


# --------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------


def route_telegram_message(
    text: str,
    *,
    chat_id: Optional[int] = None,
) -> str:
    """Parse a Telegram message and dispatch to the appropriate command.

    Args:
        text: Raw message text (may include leading /).
        chat_id: Telegram chat ID for session tracking.

    Returns:
        A string response formatted for Telegram (markdown-friendly).
        Returns an error message if the command is unknown.
    """
    if not text:
        return "Empty message."

    text = text.strip()

    # ------------------------------------------------------------------
    # /checkin
    # ------------------------------------------------------------------
    if text.startswith("/checkin"):
        return _handle_checkin(text, chat_id)

    # ------------------------------------------------------------------
    # /experiment
    # ------------------------------------------------------------------
    if text.startswith("/experiment"):
        return _handle_experiment(text)

    # ------------------------------------------------------------------
    # /patterns
    # ------------------------------------------------------------------
    if text.startswith("/patterns"):
        return _handle_patterns(text)

    # ------------------------------------------------------------------
    # /reflex
    # ------------------------------------------------------------------
    if text.startswith("/reflex"):
        return _handle_reflex(text)

    # ------------------------------------------------------------------
    # /review
    # ------------------------------------------------------------------
    if text.startswith("/review"):
        return _handle_review(text)

    # ------------------------------------------------------------------
    # /override
    # ------------------------------------------------------------------
    if text.startswith("/override"):
        return _handle_override(text)

    # ------------------------------------------------------------------
    # /pause (status check)
    # ------------------------------------------------------------------
    if text.startswith("/pause"):
        return _handle_pause_status(text)

    # ------------------------------------------------------------------
    # Unknown
    # ------------------------------------------------------------------
    return (
        "Unknown command. Try:\\n"
        "/checkin\\n"
        "/experiment create <name>\\n"
        "/experiment list\\n"
        "/patterns\\n"
        "/reflex <question>\\n"
        "/review\\n"
        "/override <reason>\\n"
        "/reflex pause today\\n"
        "/reflex resume"
    )


# ------------------------------------------------------------------------------------------------------------------------------------------
# Command handlers
# ------------------------------------------------------------------------------------------------------------------------------------------


def _handle_checkin(text: str, chat_id: Optional[int]) -> str:
    """Handle /checkin and check-in answers.

    Accepts answers in the form: key=value or just the answer text for the
    next question in sequence.
    """
    # Check for key=value style answers (e.g. "energy=8")
    kv_match = re.match(r"^/checkin\s+(\w+)=(.+)$", text)
    if kv_match:
        key, value = kv_match.group(1), kv_match.group(2).strip()
        session = CheckinSession.get(chat_id or 0)

        if key == "energy":
            try:
                session["energy"] = int(value)
            except ValueError:
                return "⚡ Energy must be a number 1-10."
        else:
            session[key] = value

        # Check if all required fields are filled
        return _finish_or_continue_checkin(chat_id, session)

    # Check for bare answer (next question in sequence)
    bare_match = re.match(r"^/checkin\s+(.+)$", text)
    if bare_match:
        answer = bare_match.group(1).strip()
        session = CheckinSession.get(chat_id or 0)
        # Map answer to the next unfilled question
        return _handle_bare_checkin_answer(chat_id, answer, session)

    # No arguments — start check-in
    session = CheckinSession.get(chat_id or 0)
    session.clear()
    return _build_checkin_prompt(session)


def _finish_or_continue_checkin(chat_id: Optional[int], session: dict) -> str:
    """Check if check-in is complete, or return the next prompt."""
    required = ["energy", "available_time", "biggest_friction",
                "main_focus", "what_shipped", "what_got_avoided"]
    missing = [k for k in required if k not in session or not session[k]]
    if missing:
        return _build_checkin_prompt(session)
    # All done — write and summarize
    result = run_checkin(
        energy=session.get("energy"),
        available_time=session.get("available_time"),
        biggest_friction=session.get("biggest_friction"),
        main_focus=session.get("main_focus"),
        what_shipped=session.get("what_shipped"),
        what_got_avoided=session.get("what_got_avoided"),
        notes=session.get("notes"),
    )
    CheckinSession.clear(chat_id or 0)
    summary = format_checkin_summary(
        energy=session.get("energy"),
        available_time=session.get("available_time"),
        biggest_friction=session.get("biggest_friction"),
        main_focus=session.get("main_focus"),
        what_shipped=session.get("what_shipped"),
        what_got_avoided=session.get("what_got_avoided"),
    )
    return f"{result}\n\n{summary}"


def _handle_bare_checkin_answer(chat_id: Optional[int], answer: str, session: dict) -> str:
    """Map a bare answer to the next missing check-in question."""
    required = ["energy", "available_time", "biggest_friction",
                "main_focus", "what_shipped", "what_got_avoided"]
    for key in required:
        if key not in session or not session[key]:
            if key == "energy":
                try:
                    val = int(answer)
                    if not (1 <= val <= 10):
                        return "⚡ Energy must be 1-10. Try again:"
                    session[key] = val
                except ValueError:
                    return "⚡ Energy must be a number 1-10. Try again:"
            else:
                session[key] = answer
            return _finish_or_continue_checkin(chat_id, session)
    # All filled
    return _finish_or_continue_checkin(chat_id, session)


def _build_checkin_prompt(session: dict) -> str:
    """Build the next check-in prompt showing missing questions."""
    required = ["energy", "available_time", "biggest_friction",
                "main_focus", "what_shipped", "what_got_avoided"]
    missing = [k for k in required if k not in session or not session[k]]

    prompt_lines = ["*Check-in* — answer any missing fields:"]

    if "energy" in missing:
        prompt_lines.append("⚡ Energy 1-10?")
    if "available_time" in missing:
        prompt_lines.append("⏱️ Available time? (e.g. 2hrs, half day)")
    if "biggest_friction" in missing:
        prompt_lines.append("🔴 Biggest friction?")
    if "main_focus" in missing:
        prompt_lines.append("🎯 Main focus today?")
    if "what_shipped" in missing:
        prompt_lines.append("🚀 What shipped recently?")
    if "what_got_avoided" in missing:
        prompt_lines.append("🛑 What got avoided?")

    prompt_lines.append("\n_Reply with key=value or just your answer._")
    return "\n".join(prompt_lines)


def _handle_experiment(text: str) -> str:
    """Handle /experiment create <name> or /experiment list."""
    match = re.match(r"^/experiment\s+create\s+(.+)$", text)
    if match:
        name = match.group(1).strip()
        try:
            return run_experiment_create(name=name)
        except Exception as exc:
            log.warning("[Reflex] experiment create failed: %s", exc)
            return f"Failed to create experiment: {exc}"

    # /experiment list
    if re.match(r"^/experiment\s+list\s*$", text, re.IGNORECASE):
        return run_experiment_list()

    # Bare /experiment
    if text.strip() == "/experiment":
        return (
            "*Usage:*\\n"
            "/experiment create <name>\\n"
            "/experiment list"
        )

    return (
        "*Usage:*\\n"
        "/experiment create <name>\\n"
        "/experiment list"
    )


def _handle_patterns(text: str) -> str:
    """Handle /patterns or /patterns <id>."""
    match = re.match(r"^/patterns\s+(.+)$", text)
    if match:
        pattern_id = match.group(1).strip()
        return run_patterns_detail(pattern_id)
    return run_patterns_list()


def _handle_reflex(text: str) -> str:
    """Handle /reflex <question> and /reflex pause/resume."""
    # /reflex pause today
    if re.search(r"pause\s+today", text, re.IGNORECASE):
        return run_pause("today")
    # /reflex pause week
    if re.search(r"pause\s+week", text, re.IGNORECASE):
        return run_pause("week")
    # /reflex resume
    if re.search(r"resume", text, re.IGNORECASE):
        return run_resume()

    # /reflex <question>
    match = re.match(r"^/reflex\s+(.+)$", text)
    if match:
        question = match.group(1).strip()
        try:
            return run_reflex_query(question)
        except Exception as exc:
            log.warning("[Reflex] /reflex query failed: %s", exc)
            return f"Reflex query failed: {exc}"

    return (
        "*Usage:*\\n"
        "/reflex <your question>\\n"
        "/reflex pause today\\n"
        "/reflex pause week\\n"
        "/reflex resume"
    )


def _handle_review(text: str) -> str:
    """Handle /review."""
    try:
        return run_review()
    except Exception as exc:
        log.warning("[Reflex] /review failed: %s", exc)
        return f"Failed to generate review: {exc}"


def _handle_override(text: str) -> str:
    """Handle /override <reason>."""
    match = re.match(r"^/override\s+(.+)$", text)
    if not match:
        return (
            "*Usage:*\\n"
            "/override <reason>\\n"
            "Example: /override I understand the risk but need to proceed."
        )
    reason = match.group(1).strip()
    try:
        return run_override(reason=reason)
    except Exception as exc:
        log.warning("[Reflex] /override failed: %s", exc)
        return f"Override failed: {exc}"


def _handle_pause_status(text: str) -> str:
    """Handle /pause (status check)."""
    return run_pause_status()
