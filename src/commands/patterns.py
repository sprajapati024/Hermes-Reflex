"""Reflex patterns command.

Triggered by /patterns. Subcommands:
  /patterns                    — list all patterns
  /patterns <id>               — detail for a specific pattern
  /patterns add <risk_type> [--name "..."] [--desc "..."]  — create candidate
  /patterns promote <id>       — promote candidate→watching or watching→active
  /patterns demote <id>        — demote watching→candidate or active→watching
  /patterns retire <id>        — retire (any stage → retired)
  /patterns advice <id>        — show promotion readiness for a pattern

Backward-compatible exports (Phase 7 API):
  run_patterns_list   → _handle_list
  run_patterns_detail → _handle_detail
"""

from __future__ import annotations

import re
from typing import Optional

from ..gbrain.paths import get_patterns_root
from ..gbrain.markdown import read_markdown
from ..patterns.lifecycle import (
    create_candidate,
    promote,
    demote,
    retire,
    get_status,
    get_promotion_advice,
)
from ..patterns.evidence import get_evidence_summary


def run_patterns_command(text: str) -> str:
    """Route a /patterns command to the appropriate sub-handler."""
    # Strip leading whitespace
    text = text.strip()

    # /patterns add <risk_type> [--name "..."] [--desc "..."]
    add_match = re.match(r"^/patterns\s+add\s+(\S+)\s*(.*)$", text)
    if add_match:
        risk_type = add_match.group(1)
        rest = add_match.group(2) or ""
        name_match = re.search(r"--name\s+[\"']?([^\"'-]+)[\"']?", rest)
        desc_match = re.search(r"--desc\s+[\"']?([^\"'-]+)[\"']?", rest)
        name = name_match.group(1).strip() if name_match else risk_type
        desc = desc_match.group(1).strip() if desc_match else None
        return _handle_add(risk_type, name, desc)

    # /patterns promote <id>
    promote_match = re.match(r"^/patterns\s+promote\s+(\S+)$", text)
    if promote_match:
        return _handle_promote(promote_match.group(1))

    # /patterns demote <id>
    demote_match = re.match(r"^/patterns\s+demote\s+(\S+)$", text)
    if demote_match:
        return _handle_demote(demote_match.group(1))

    # /patterns retire <id>
    retire_match = re.match(r"^/patterns\s+retire\s+(\S+)$", text)
    if retire_match:
        return _handle_retire(retire_match.group(1))

    # /patterns advice <id>
    advice_match = re.match(r"^/patterns\s+advice\s+(\S+)$", text)
    if advice_match:
        return _handle_advice(advice_match.group(1))

    # /patterns <id> — detail view
    detail_match = re.match(r"^/patterns\s+(\S+)$", text)
    if detail_match:
        return _handle_detail(detail_match.group(1))

    # Bare /patterns — list all
    return _handle_list()


# ---------------------------------------------------------------------------
# Sub-handlers
# ---------------------------------------------------------------------------

def _handle_add(risk_type: str, name: str, description: Optional[str]) -> str:
    """Create a new candidate pattern."""
    try:
        pattern_id = create_candidate(
            name=name,
            risk_type=risk_type,
            matched_terms=[],
            confidence=0.5,
            description=description,
        )
        status = get_status(pattern_id)
        return (
            f"✅ Pattern *{name}* added as *{status}*.\n"
            f"Risk type: `{risk_type}`\n"
            f"Use `/patterns promote {pattern_id}` when ready."
        )
    except Exception as e:
        return f"❌ Failed to add pattern: {e}"


def _handle_promote(pattern_id: str) -> str:
    """Promote a pattern to the next stage."""
    current = get_status(pattern_id)
    if current is None:
        return f"❌ Pattern `{pattern_id}` not found."
    if current == "retired":
        return f"❌ Can't promote a retired pattern. Create a new one with `/patterns add`."
    try:
        new_status = promote(pattern_id)
        return (
            f"⬆️ Pattern *{pattern_id}* promoted: *{current}* → *{new_status}*."
        )
    except (ValueError, FileNotFoundError) as e:
        return f"❌ Cannot promote: {e}"


def _handle_demote(pattern_id: str) -> str:
    """Demote a pattern to the previous stage."""
    current = get_status(pattern_id)
    if current is None:
        return f"❌ Pattern `{pattern_id}` not found."
    if current == "retired":
        return f"❌ Can't demote a retired pattern."
    try:
        new_status = demote(pattern_id)
        return (
            f"⬇️ Pattern *{pattern_id}* demoted: *{current}* → *{new_status}*."
        )
    except (ValueError, FileNotFoundError) as e:
        return f"❌ Cannot demote: {e}"


def _handle_retire(pattern_id: str) -> str:
    """Retire a pattern."""
    current = get_status(pattern_id)
    if current is None:
        return f"❌ Pattern `{pattern_id}` not found."
    if current == "retired":
        return f"Pattern `{pattern_id}` is already retired."
    try:
        retire(pattern_id)
        return f"⚰️ Pattern *{pattern_id}* retired."
    except FileNotFoundError as e:
        return f"❌ Cannot retire: {e}"


def _handle_advice(pattern_id: str) -> str:
    """Show promotion readiness for a pattern."""
    current = get_status(pattern_id)
    if current is None:
        return f"❌ Pattern `{pattern_id}` not found."

    advice = get_promotion_advice(pattern_id)
    evidence = get_evidence_summary(pattern_id)

    lines = [f"*Promotion Advice: {pattern_id}*"]
    lines.append(f"Current status: *{advice['current_status']}*")

    next_status = advice.get("next_status")
    if next_status:
        lines.append(f"Next stage: *{next_status}*")
        met = advice["requirements_met"]
        lines.append(f"Ready: {'✅ Yes' if met else '⏳ Not yet'}")

    blockers = advice.get("blockers", [])
    if blockers:
        lines.append("\n*Requirements:*")
        for b in blockers:
            lines.append(f"  • {b}")

    # Signal summary
    signals = evidence.get("signals_in_window", 0)
    days = evidence.get("days_since_firing")
    if signals is not None:
        lines.append(f"\n*Evidence:* {signals} signal(s) in last 14 days")
    if days is not None:
        lines.append(f"Last firing: {days} day(s) ago")
    elif advice["current_status"] == "active":
        lines.append("Last firing: never recorded")

    has_int = advice.get("has_intervention", False)
    lines.append(f"Has intervention: {'✅' if has_int else '❌'}")

    return "\n".join(lines)


def _handle_list() -> str:
    """List active, watching, and candidate patterns."""
    root = get_patterns_root()

    def _load_patterns(status: str) -> list[dict]:
        results = []
        dir_path = root / status
        if not dir_path.exists():
            return results
        for f in sorted(dir_path.glob("*.md")):
            try:
                data, _ = read_markdown(f)
                results.append(data)
            except Exception:
                continue
        return results

    active = _load_patterns("active")
    watching = _load_patterns("watching")
    candidate = _load_patterns("candidate")
    retired = _load_patterns("retired")

    lines = ["*Reflex Patterns*"]

    if not active and not watching and not candidate and not retired:
        lines.append("No patterns yet. Use `/patterns add <risk_type>` to create one.")
        return "\n".join(lines)

    # Status emoji map
    emoji = {"active": "🟢", "watching": "🟡", "candidate": "⚪", "retired": "⚫"}

    for status, label, patterns in [
        ("active", "Active", active),
        ("watching", "Watching", watching),
        ("candidate", "Candidate", candidate),
    ]:
        if patterns:
            lines.append(f"\n*{label}*")
            for p in patterns:
                e = emoji[status]
                evid = p.get("evidence_count", 0)
                conf = p.get("confidence", 0)
                lines.append(
                    f"{e} `{p.get('id', p.get('name', '?'))}` "
                    f"— {p.get('name', '?')} "
                    f"(sig:{evid}, conf:{conf:.0%})"
                )

    if retired:
        lines.append(f"\n*Retired* ({len(retired)})")
        for p in retired[:5]:  # Show max 5 retired
            lines.append(f"⚫ `{p.get('id', '?')}` — {p.get('name', '?')}")
        if len(retired) > 5:
            lines.append(f"  ...and {len(retired) - 5} more")

    lines.append("\n_CRU: `/patterns add|promote|demote|retire|advice <id>`_")
    return "\n".join(lines)


def _handle_detail(pattern_id: str) -> str:
    """Get detail for a specific pattern."""
    from ..gbrain.storage import read_pattern

    # Try all statuses
    for status in ("active", "watching", "candidate", "retired"):
        try:
            data, body = read_pattern(pattern_id, status)
            break
        except FileNotFoundError:
            continue
    else:
        return f"❌ Pattern `{pattern_id}` not found."

    emoji = {"active": "🟢", "watching": "🟡", "candidate": "⚪", "retired": "⚫"}
    e = emoji.get(data.get("status", ""), "⚪")

    lines = [f"{e} *Pattern: {data.get('name', pattern_id)}*"]
    lines.append(f"ID: `{data.get('id', pattern_id)}`")
    lines.append(f"Status: *{data.get('status', '?').capitalize()}*")
    conf = data.get("confidence", 0)
    lines.append(f"Confidence: {conf:.0%}" if conf else "Confidence: ?")
    lines.append(f"Evidence: {data.get('evidence_count', 0)} signals")

    risk = data.get("risk_type", "")
    if risk:
        lines.append(f"Risk type: `{risk}`")

    intervention = data.get("intervention", "")
    if intervention:
        lines.append(f"\n*Intervention:*\n_{intervention}_")

    # Promotion advice inline
    advice = get_promotion_advice(pattern_id)
    next_status = advice.get("next_status")
    if next_status and data.get("status") != "retired":
        met = "✅" if advice["requirements_met"] else "⏳"
        lines.append(f"\n Next stage: *{next_status}* ({met})")

    if body and body.strip():
        lines.append(f"\n{body.strip()}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Backward-compatible exports (Phase 7 API)
# ---------------------------------------------------------------------------
run_patterns_list = _handle_list
run_patterns_detail = _handle_detail
