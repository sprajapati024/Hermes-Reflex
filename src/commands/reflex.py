"""Reflex manual query command.

Triggered by /reflex <question>. Runs the full middleware pipeline manually
and returns the recommendation — useful for testing and on-demand checks.
"""

from __future__ import annotations

from typing import Optional

from ..core.middleware import process_reflex


def run_reflex_query(
    question: str,
    *,
    project: Optional[str] = None,
    skip_retrieval: bool = False,
    skip_critic: bool = False,
) -> str:
    """Run the full Reflex middleware on a question and return the result.

    This is the same pipeline used automatically for every user message,
    but triggered manually via /reflex.
    """
    if not question or not question.strip():
        return "Usage: /reflex <your question>"

    result = process_reflex(
        user_message=question,
        project=project,
        include_reflex_instructions=True,
        skip_retrieval=skip_retrieval,
        skip_critic=skip_critic,
    )

    # Format for Telegram
    lines = [f"*Reflex Analysis*"]

    mode = result.mode
    lines.append(f"Mode: {mode}")

    if result.risk_type and result.risk_type != "none":
        lines.append(f"Risk: {result.risk_type}")

    if result.confidence > 0:
        lines.append(f"Confidence: {result.confidence:.0%}")

    if result.evidence:
        lines.append(f"Evidence: {len(result.evidence)} item(s)")
        for ev in result.evidence[:3]:
            title = ev.get("title") or ev.get("path", "unknown")
            score = ev.get("score", 0)
            lines.append(f"  • [{score:.0%}] {title}")

    if result.hermes_instruction:
        lines.append(f"\n{result.hermes_instruction}")

    if result.decision_id:
        lines.append(f"\n_ID: {result.decision_id}_")

    return "\n".join(lines)
