"""Skillify candidates for Hermes Reflex — Phase 10.

Convert repeated useful interventions into reusable Hermes skills.

Trigger conditions (all must be true):
  1. Pattern fires >= 5 times in its lifetime
  2. Useful intervention accepted >= 2 times
  3. Pattern is not retired

Workflow:
  1. Run detect_skillify_candidates() — returns patterns ready for skillify
  2. For each candidate, run create_candidate() — writes file to gbrain and
     returns a Telegram approval message
  3. When user approves, run approve_candidate(skill_name) — creates the skill
     and removes the candidate file
  4. Reject or discard candidate files that are not approved

Skillify candidates live at:
  gbrain/reflex/skillify-candidates/<skill_name>.md
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..gbrain.paths import (
    get_reflex_root,
    get_patterns_root,
    get_skillify_root,
    get_skillify_candidate_path,
    get_interventions_root,
)
from ..gbrain.markdown import read_markdown, write_markdown
from ..patterns.evidence import get_evidence_summary


# --------------------------------------------------------------------------
# Thresholds (from IMPLEMENTATION_PLAN)
# --------------------------------------------------------------------------

MIN_PATTERN_FIRES = 5       # total fires to qualify
MIN_USEFUL_INTERVENTIONS = 2  # accepted interventions
SKILLIFY_WINDOW_DAYS = 30     # consider interventions in last 30 days


# --------------------------------------------------------------------------
# Candidate detection
# --------------------------------------------------------------------------


def _load_all_patterns() -> list[tuple[str, str, dict]]:
    """Return [(pattern_id, status, frontmatter)] for all non-retired patterns."""
    patterns_root = get_patterns_root()
    results = []
    for status in ("active", "watching", "candidate"):
        status_dir = patterns_root / status
        if not status_dir.exists():
            continue
        for f in status_dir.glob("*.md"):
            try:
                data, _ = read_markdown(f)
                results.append((f.stem, status, data))
            except Exception:
                continue
    return results


def _count_interventions_in_window(
    pattern_id: str,
    window_days: int = SKILLIFY_WINDOW_DAYS,
) -> int:
    """Count useful interventions for a pattern in the last N days."""
    from datetime import timedelta

    interventions_root = get_interventions_root()
    if not interventions_root.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=window_days)
    count = 0
    for f in interventions_root.rglob("*.md"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime >= cutoff:
                data, _ = read_markdown(f)
                risk_type = data.get("risk_type", "")
                if risk_type == pattern_id:
                    count += 1
        except Exception:
            continue
    return count


def detect_skillify_candidates() -> list[dict]:
    """Scan active/watching/candidate patterns and return those ready for skillify.

    Returns a list of dicts with:
      pattern_id, pattern_name, status, fire_count,
      useful_interventions, skill_name, reason
    """
    candidates = []
    patterns = _load_all_patterns()

    for pattern_id, status, data in patterns:
        # Skip retired
        if status == "retired":
            continue

        evidence = get_evidence_summary(pattern_id)
        fire_count = evidence.get("total_signals", 0)

        # Count useful interventions in window
        useful = _count_interventions_in_window(pattern_id)

        if fire_count >= MIN_PATTERN_FIRES and useful >= MIN_USEFUL_INTERVENTIONS:
            # Generate a skill-friendly name from the pattern
            risk_type = data.get("risk_type", pattern_id)
            intervention = data.get("intervention", "")
            pattern_name = data.get("name", risk_type.replace("-", " ").replace("_", " ").title())

            skill_name = _make_skill_name(risk_type)

            reason = (
                f"Fired {fire_count}x with {useful} accepted interventions. "
                f"Intervention: {intervention[:80]}"
            )

            candidates.append({
                "pattern_id": pattern_id,
                "pattern_name": pattern_name,
                "status": status,
                "fire_count": fire_count,
                "useful_interventions": useful,
                "skill_name": skill_name,
                "intervention": intervention,
                "reason": reason,
            })

    return candidates


# --------------------------------------------------------------------------
# Skill name generation
# --------------------------------------------------------------------------


def _make_skill_name(risk_type: str) -> str:
    """Convert a risk_type slug into a skill name.

    Examples:
      ui_avoidance -> avoid-ui-builds
      planning_loop -> escape-planning-loop
      overbuild_risk -> prevent-overbuild
    """
    prefix_map = {
        "ui_avoidance": "avoid",
        "planning_loop": "escape",
        "overbuild_risk": "prevent",
        "project_switching": "finish-before-switching",
        "integration_avoidance": "tackle-integration",
        "contract_conflict": "honor-contract",
        "experiment_conflict": "respect-experiment",
    }
    prefix = prefix_map.get(risk_type, "handle")
    # Remove common suffixes
    clean = re.sub(r"(_risk|_avoidance|_loop|_switching|_conflict)?$", "", risk_type)
    # Normalize underscores to hyphens for readability
    clean = clean.replace("_", "-")
    return f"{prefix}-{clean}"


# --------------------------------------------------------------------------
# Candidate file management
# --------------------------------------------------------------------------

def _build_skillify_candidate_body(
    skill_name: str,
    pattern_id: str,
    pattern_name: str,
    intervention: str,
    fire_count: int,
    useful_interventions: int,
) -> str:
    """Build the body text for a skillify candidate file."""
    body = f"## Trigger\n"
    body += f"When the user expresses intent related to: *{pattern_name}*\n\n"
    body += f"## Detection\n"
    body += f"- Pattern ID: `{pattern_id}`\n"
    body += f"- Fires: {fire_count}x total\n"
    body += f"- Useful interventions: {useful_interventions}x in last {SKILLIFY_WINDOW_DAYS} days\n\n"
    body += f"## Intervention (Tested)\n{intervention}\n\n"
    body += f"## Checklist\n"
    body += f"- [ ] User has expressed intent related to {pattern_name}\n"
    body += f"- [ ] Reflex fired this pattern\n"
    body += f"- [ ] State the intervention clearly\n"
    body += f"- [ ] Confirm user understands before proceeding\n\n"
    body += f"## Response Behavior\n"
    body += f"When this skill fires, respond with:\n\n"
    body += f'1. Name the pattern: "{pattern_name} detected."\n'
    body += f"2. State the evidence: \"This has fired {fire_count} times.\"\n"
    body += f"3. Give the intervention: \"{intervention}\"\n"
    body += f"4. Wait for user confirmation before proceeding.\n"
    return body


def create_candidate(
    pattern_id: str,
    skill_name: Optional[str] = None,
    intervention: Optional[str] = None,
    fire_count: Optional[int] = None,
    useful_interventions: Optional[int] = None,
    pattern_name: Optional[str] = None,
) -> dict:
    """Write a skillify candidate file to GBrain.

    Args:
        pattern_id: The pattern's slug (e.g. "ui_avoidance")
        skill_name: Optional override for the generated skill name
        intervention: Optional override (pulled from pattern if not provided)
        fire_count: Optional override
        useful_interventions: Optional override
        pattern_name: Optional override

    Returns a dict with:
        path: absolute path of the candidate file
        skill_name: the skill name used
        message: Telegram-formatted approval request
        already_exists: bool
    """
    # Load pattern data if not provided
    patterns_root = get_patterns_root()
    pattern_data = None
    pattern_status = None

    for status in ("active", "watching", "candidate"):
        p = patterns_root / status / f"{pattern_id}.md"
        if p.exists():
            try:
                pattern_data, _ = read_markdown(p)
                pattern_status = status
                break
            except Exception:
                pass

    if pattern_data is None:
        raise FileNotFoundError(f"Pattern '{pattern_id}' not found.")

    evidence = get_evidence_summary(pattern_id)

    skill_name = skill_name or _make_skill_name(pattern_id)
    intervention = intervention or pattern_data.get("intervention", "")
    fire_count = fire_count or evidence.get("total_signals", 0)
    useful_interventions = (
        useful_interventions
        or _count_interventions_in_window(pattern_id)
    )
    pattern_name = pattern_name or pattern_data.get("name", pattern_id.replace("-", " ").replace("_", " ").title())

    candidate_path = get_skillify_candidate_path(skill_name)
    candidate_path.parent.mkdir(parents=True, exist_ok=True)

    already_exists = candidate_path.exists()

    data = {
        "id": skill_name,
        "type": "skillify-candidate",
        "pattern_id": pattern_id,
        "pattern_status": pattern_status,
        "skill_name": skill_name,
        "fire_count": fire_count,
        "useful_interventions": useful_interventions,
        "created_at": datetime.now().isoformat(),
        "status": "pending",
    }

    body = _build_skillify_candidate_body(
        skill_name=skill_name,
        pattern_id=pattern_id,
        pattern_name=pattern_name,
        intervention=intervention,
        fire_count=fire_count,
        useful_interventions=useful_interventions,
    )

    write_markdown(candidate_path, body, data)

    # Build Telegram approval message
    msg_lines = [
        f"*Skillify Candidate: {skill_name}*",
        "",
        f"Pattern: {pattern_name} (`{pattern_id}`)",
        f"Status: {pattern_status}",
        f"Fires: {fire_count}x | Useful interventions: {useful_interventions}x",
        "",
        f"*Intervention:* {intervention[:120]}",
        "",
        "Approve?",
        f"/skillify approve {skill_name}",
        f"/skillify reject {skill_name}",
    ]

    return {
        "path": str(candidate_path),
        "skill_name": skill_name,
        "message": "\n".join(msg_lines),
        "already_exists": already_exists,
    }


def list_candidates(status: Optional[str] = None) -> list[dict]:
    """List skillify candidates.

    Args:
        status: Filter by status (pending/approved/rejected). None = all.

    Returns list of dicts with id, skill_name, pattern_id, created_at, status.
    """
    skillify_root = get_skillify_root()
    if not skillify_root.exists():
        return []

    results = []
    for f in skillify_root.glob("*.md"):
        try:
            data, _ = read_markdown(f)
            if status and data.get("status") != status:
                continue
            results.append({
                "path": str(f),
                "id": data.get("id", f.stem),
                "skill_name": data.get("skill_name", f.stem),
                "pattern_id": data.get("pattern_id", ""),
                "created_at": data.get("created_at", ""),
                "status": data.get("status", "pending"),
                "fire_count": data.get("fire_count", 0),
                "useful_interventions": data.get("useful_interventions", 0),
            })
        except Exception:
            continue
    return sorted(results, key=lambda x: x.get("created_at", ""))


def approve_candidate(skill_name: str) -> dict:
    """Mark candidate as approved and prepare it for skill creation.

    Returns dict with path and a summary message.
    """
    candidate_path = get_skillify_candidate_path(skill_name)
    if not candidate_path.exists():
        raise FileNotFoundError(f"Candidate '{skill_name}' not found.")

    data, body = read_markdown(candidate_path)
    data["status"] = "approved"
    data["approved_at"] = datetime.now().isoformat()
    write_markdown(candidate_path, body, data)

    return {
        "path": str(candidate_path),
        "skill_name": skill_name,
        "message": (
            f"Approved: {skill_name}\n"
            f"Pattern: {data.get('pattern_id', '')}\n"
            f"Ready for skill creation."
        ),
    }


def reject_candidate(skill_name: str) -> dict:
    """Mark candidate as rejected and archive it."""
    candidate_path = get_skillify_candidate_path(skill_name)
    if not candidate_path.exists():
        raise FileNotFoundError(f"Candidate '{skill_name}' not found.")

    data, body = read_markdown(candidate_path)
    data["status"] = "rejected"
    data["rejected_at"] = datetime.now().isoformat()
    # Move to rejected subdir if it exists, otherwise rename
    rejected_dir = candidate_path.parent / "rejected"
    rejected_dir.mkdir(exist_ok=True)
    new_path = rejected_dir / candidate_path.name
    write_markdown(new_path, body, data)
    candidate_path.unlink()

    return {
        "path": str(new_path),
        "skill_name": skill_name,
        "message": f"Rejected and archived: {skill_name}",
    }


def read_candidate(skill_name: str) -> tuple[dict, str]:
    """Read a candidate file. Returns (frontmatter, body)."""
    candidate_path = get_skillify_candidate_path(skill_name)
    return read_markdown(candidate_path)


# --------------------------------------------------------------------------
# Telegram command integration helpers
# --------------------------------------------------------------------------

def skillify_status_message() -> str:
    """Return a Telegram-formatted summary of all pending candidates."""
    pending = list_candidates(status="pending")
    if not pending:
        return "*Skillify:* No pending candidates.\nRun `/skillify scan` to detect new ones."

    lines = [f"*Skillify:* {len(pending)} pending candidate(s)\n"]
    for c in pending:
        lines.append(
            f"  • {c['skill_name']} "
            f"(fires: {c['fire_count']}, "
            f"interventions: {c['useful_interventions']})"
        )
    lines.append("\nApprove: /skillify approve <name>")
    lines.append("Reject:  /skillify reject <name>")
    return "\n".join(lines)


def scan_and_create_candidates() -> str:
    """Run detection and create candidate files for all qualifying patterns.

    Returns a Telegram message summarizing what was created.
    """
    candidates = detect_skillify_candidates()
    if not candidates:
        return (
            "*Skillify scan:* No patterns met the threshold.\n"
            f"Need >= {MIN_PATTERN_FIRES} fires + "
            f">= {MIN_USEFUL_INTERVENTIONS} useful interventions."
        )

    skillify_root = get_skillify_root()
    skillify_root.mkdir(parents=True, exist_ok=True)

    lines = [f"*Skillify:* {len(candidates)} new candidate(s)\n"]
    for c in candidates:
        skill_name = c["skill_name"]
        # Skip if already exists
        existing_path = get_skillify_candidate_path(skill_name)
        if existing_path.exists():
            lines.append(f"  (already exists) {skill_name}")
            continue

        create_candidate(
            pattern_id=c["pattern_id"],
            skill_name=skill_name,
            intervention=c["intervention"],
            fire_count=c["fire_count"],
            useful_interventions=c["useful_interventions"],
            pattern_name=c["pattern_name"],
        )
        lines.append(f"  + {skill_name} (fires: {c['fire_count']})")

    lines.append("\nReview with /skillify status")
    return "\n".join(lines)
