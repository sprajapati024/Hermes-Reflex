"""Pattern lifecycle management for Hermes Reflex.

Transitions patterns through states:
  candidate → watching → active → retired

Usage:
    from src.patterns.lifecycle import promote, demote, retire, create_candidate

    # Create a new candidate
    create_candidate(risk_type="ui_avoidance", name="UI Avoidance Tendency",
                     matched_terms=["dashboard"], confidence=0.75)

    # Promote to watching
    promote("ui_avoidance")   # candidate → watching

    # Demote back
    demote("ui_avoidance")     # watching → candidate

    # Retire
    retire("ui_avoidance")     # active → retired
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from ..gbrain.paths import get_patterns_root, get_pattern_path
from ..gbrain.markdown import read_markdown, write_markdown
from ..gbrain.storage import write_pattern
from .evidence import (
    CANDIDATE_TO_WATCHING_SIGNALS,
    WATCHING_TO_ACTIVE_SIGNALS,
    get_evidence_summary,
    count_signals_in_window,
    has_useful_intervention,
)


# Valid lifecycle transitions
VALID_TRANSITIONS = {
    "candidate": ["watching", "retired"],
    "watching":  ["active",   "candidate", "retired"],
    "active":    ["retired"],
    "retired":   [],
}


def _slugify(text: str) -> str:
    """Create a slug from pattern name or risk type."""
    return text.lower().replace(" ", "-").replace("_", "-")


def create_candidate(
    *,
    name: str,
    risk_type: str,
    matched_terms: list[str],
    confidence: float,
    description: Optional[str] = None,
) -> str:
    """Create a new candidate pattern.

    Args:
        name: Human-readable name for the pattern
        risk_type: e.g. "ui_avoidance", "planning_loop"
        matched_terms: list of terms that triggered this
        confidence: initial confidence score (0.0-1.0)

    Returns:
        The pattern_id
    """
    pattern_id = _slugify(risk_type) if not name else _slugify(name)
    patterns_root = get_patterns_root()
    candidate_dir = patterns_root / "candidate"
    candidate_dir.mkdir(parents=True, exist_ok=True)

    # Check if already exists
    existing = candidate_dir / f"{pattern_id}.md"
    if existing.exists():
        # Update evidence instead
        data, body = read_markdown(existing)
        data["evidence_count"] = data.get("evidence_count", 0) + 1
        data["confidence"] = max(float(data.get("confidence", 0)), confidence)
        data["last_seen"] = datetime.now().date().isoformat()
        write_markdown(existing, body, data)
        return pattern_id

    intervention = _default_intervention(risk_type)
    write_pattern(
        pattern_id=pattern_id,
        name=name,
        status="candidate",
        confidence=confidence,
        evidence_count=1,
        intervention=intervention,
        description=description or f"Detected from terms: {', '.join(matched_terms)}",
        risk_type=risk_type,
        last_seen=datetime.now().date().isoformat(),
    )
    return pattern_id


def promote(pattern_id: str) -> str:
    """Promote a pattern to the next lifecycle stage.

    Transitions:
      candidate → watching
      watching  → active

    Returns the new status.

    Raises:
        ValueError if transition is not valid.
    """
    patterns_root = get_patterns_root()

    # Find the current file
    src_status: Optional[str] = None
    src_path: Optional[Path] = None
    for status in ("candidate", "watching", "active"):
        p = patterns_root / status / f"{pattern_id}.md"
        if p.exists():
            src_status = status
            src_path = p
            break

    if src_status is None or src_path is None:
        raise FileNotFoundError(f"Pattern '{pattern_id}' not found.")

    valid_next = VALID_TRANSITIONS.get(src_status, [])
    if not valid_next:
        raise ValueError(
            f"Cannot promote pattern '{pattern_id}': no valid transitions from '{src_status}'."
        )

    next_status = valid_next[0]
    data, body = read_markdown(src_path)
    data["status"] = next_status
    data["promoted_at"] = datetime.now().isoformat()
    dst = patterns_root / next_status / f"{pattern_id}.md"
    write_markdown(dst, body, data)
    src_path.unlink()
    return next_status


def demote(pattern_id: str) -> str:
    """Demote a pattern to the previous lifecycle stage.

    Transitions:
      watching → candidate
      active   → watching

    Returns the new status.

    Raises:
        ValueError if transition is not valid.
    """
    patterns_root = get_patterns_root()

    # Find the current file
    src_status: Optional[str] = None
    src_path: Optional[Path] = None
    for status in ("active", "watching", "candidate"):
        p = patterns_root / status / f"{pattern_id}.md"
        if p.exists():
            src_status = status
            src_path = p
            break

    if src_status is None or src_path is None:
        raise FileNotFoundError(f"Pattern '{pattern_id}' not found.")

    valid_next = _DEMOTE_TRANSITIONS.get(src_status, [])
    if not valid_next:
        raise ValueError(
            f"Cannot demote pattern '{pattern_id}': no valid transitions from '{src_status}'."
        )

    next_status = valid_next[0]
    data, body = read_markdown(src_path)
    data["status"] = next_status
    data["demoted_at"] = datetime.now().isoformat()
    dst = patterns_root / next_status / f"{pattern_id}.md"
    write_markdown(dst, body, data)
    src_path.unlink()
    return next_status


def retire(pattern_id: str) -> str:
    """Retire a pattern (active or watching → retired).

    Idempotent: retiring an already-retired pattern returns "retired" without error.

    Returns "retired".

    Raises:
        FileNotFoundError if the pattern does not exist in any non-retired stage.
    """
    patterns_root = get_patterns_root()
    # Check if already retired
    retired_path = patterns_root / "retired" / f"{pattern_id}.md"
    if retired_path.exists():
        return "retired"

    for status in ("active", "watching", "candidate"):
        src = patterns_root / status / f"{pattern_id}.md"
        if src.exists():
            data, body = read_markdown(src)
            dst = patterns_root / "retired" / f"{pattern_id}.md"
            data["status"] = "retired"
            data["retired_at"] = datetime.now().isoformat()
            write_markdown(dst, body, data)
            src.unlink()
            return "retired"
    raise FileNotFoundError(
        f"Pattern '{pattern_id}' not found in active, watching, or candidate."
    )


def get_status(pattern_id: str) -> Optional[str]:
    """Return the current status of a pattern, or None if not found."""
    patterns_root = get_patterns_root()
    for status in ("candidate", "watching", "active", "retired"):
        if (patterns_root / status / f"{pattern_id}.md").exists():
            return status
    return None


def get_promotion_advice(pattern_id: str) -> dict:
    """Return promotion readiness for a pattern.

    Returns a dict with:
      current_status, next_status, requirements_met,
      signals_needed, has_intervention, blockers
    """
    status = get_status(pattern_id)
    if status is None:
        return {"error": f"Pattern '{pattern_id}' not found"}

    evidence = get_evidence_summary(pattern_id)
    blockers = []
    signals_needed = 0

    if status == "candidate":
        signals = count_signals_in_window(pattern_id, 14)
        needed = CANDIDATE_TO_WATCHING_SIGNALS
        signals_needed = max(0, needed - signals)
        if evidence["candidate_threshold_met"]:
            blockers.append("ready to promote")
        else:
            blockers.append(f"need {signals_needed} more signal(s) in 14 days")
        return {
            "current_status": status,
            "next_status": "watching",
            "requirements_met": evidence["candidate_threshold_met"],
            "signals_needed": signals_needed,
            "has_intervention": evidence["has_intervention"],
            "blockers": blockers,
        }

    if status == "watching":
        signals = count_signals_in_window(pattern_id, 14)
        needed = WATCHING_TO_ACTIVE_SIGNALS
        signals_needed = max(0, needed - signals)
        blockers_list = []
        if signals < needed:
            blockers_list.append(f"need {signals_needed} more signal(s) in 14 days")
        if not evidence["has_intervention"]:
            blockers_list.append("no useful intervention recorded yet")
        return {
            "current_status": status,
            "next_status": "active",
            "requirements_met": evidence["watching_threshold_met"],
            "signals_needed": signals_needed,
            "has_intervention": evidence["has_intervention"],
            "blockers": blockers_list,
        }

    if status == "active":
        days = evidence["days_since_firing"]
        blockers_list = []
        if days is not None and days >= 30:
            blockers_list.append("eligible for retirement (30+ days inactive)")
        elif days is not None:
            blockers_list.append(f"{30 - days} days until eligible for retirement")
        else:
            blockers_list.append("no retirement pressure")
        return {
            "current_status": status,
            "next_status": "retired",
            "requirements_met": evidence["retire_threshold_met"],
            "signals_needed": 0,
            "has_intervention": evidence["has_intervention"],
            "blockers": blockers_list,
        }

    return {
        "current_status": status,
        "next_status": None,
        "requirements_met": False,
        "signals_needed": 0,
        "has_intervention": False,
        "blockers": ["already retired"],
    }


# ---------------------------------------------------------------------------
# Reverse of promote transitions: active→watching, watching→candidate.
# Hardcoded to avoid order-reversal bugs from computed inverses.
_DEMOTE_TRANSITIONS: dict[str, list[str]] = {
    "active":   ["watching"],
    "watching": ["candidate"],
    "candidate": [],
}


def _inverse_transitions() -> dict:
    """Return inverse of VALID_TRANSITIONS for demotion."""
    inv = {}
    for from_status, to_list in VALID_TRANSITIONS.items():
        for to in to_list:
            inv.setdefault(from_status, []).append(to)
    return inv


def _default_intervention(risk_type: str) -> str:
    """Return a default intervention message for a known risk type."""
    interventions = {
        "planning_loop": "Before starting a new planning session, ask: what's the smallest concrete next step?",
        "ui_avoidance": "Remember: no dashboard until the core loop works. Ship the reflex first.",
        "project_switching": "What's the current project milestone? Finish it before starting anything new.",
        "integration_avoidance": "What's the simplest integration that solves the immediate problem?",
        "overbuild_risk": "Ask: what's the absolute minimum? Build only what you need right now.",
        "contract_conflict": "This conflicts with the current operating contract. Use /override if you want to proceed.",
        "experiment_conflict": "This experiment is still running. Evaluate it before starting a replacement.",
    }
    return interventions.get(
        risk_type,
        "Pause and ask: what's the actual problem I'm trying to solve right now?",
    )
