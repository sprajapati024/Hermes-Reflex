"""Reflex patterns command.

Triggered by /patterns. Returns active and watching patterns with evidence
from gbrain/reflex/patterns/.
"""

from __future__ import annotations

from pathlib import Path

from ..gbrain.paths import get_patterns_root
from ..gbrain.markdown import read_markdown


def run_patterns_list() -> str:
    """List active and watching patterns with evidence counts."""
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

    lines = ["*Reflex Patterns*"]

    if not active and not watching and not candidate:
        lines.append("No patterns detected yet.")
        return "\n".join(lines)

    if active:
        lines.append("\n*Active*")
        for p in active:
            evidence = p.get("evidence_count", 0)
            intervention = p.get("intervention", "")
            risk = p.get("risk_type", "")
            lines.append(f"• [{risk}] {p.get('name', '?')} — {evidence} signals")
            if intervention:
                lines.append(f"  → {intervention}")

    if watching:
        lines.append("\n*Watching*")
        for p in watching:
            evidence = p.get("evidence_count", 0)
            lines.append(f"• {p.get('name', '?')} — {evidence} signals")

    if candidate:
        lines.append("\n*Candidate*")
        for p in candidate:
            evidence = p.get("evidence_count", 0)
            lines.append(f"• {p.get('name', '?')} — {evidence} signals")

    return "\n".join(lines)


def run_patterns_detail(pattern_id: str, status: str = "active") -> str:
    """Get detail for a specific pattern."""
    from ..gbrain.storage import read_pattern

    try:
        data, body = read_pattern(pattern_id, status)
    except FileNotFoundError:
        return f"Pattern '{pattern_id}' not found in {status}."

    lines = [f"*Pattern: {data.get('name', pattern_id)}*"]
    lines.append(f"Status: {data.get('status', status)}")
    lines.append(f"Confidence: {data.get('confidence', '?')}")
    lines.append(f"Evidence: {data.get('evidence_count', 0)} signals")
    risk = data.get("risk_type", "")
    if risk:
        lines.append(f"Risk type: {risk}")

    intervention = data.get("intervention", "")
    if intervention:
        lines.append(f"\n*Intervention:*\n{intervention}")

    if body and body.strip():
        lines.append(f"\n{body.strip()}")

    return "\n".join(lines)
