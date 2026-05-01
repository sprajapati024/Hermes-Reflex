"""Reflex experiment command.

Triggered by /experiment create <name>. Creates a structured experiment
under gbrain/reflex/experiments/active/<name>.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..gbrain.storage import write_experiment


def run_experiment_create(
    *,
    name: str,
    hypothesis: Optional[str] = None,
    rules: Optional[list[str]] = None,
    metric: Optional[str] = None,
    success_criteria: Optional[str] = None,
) -> str:
    """Create a new experiment.

    Args:
        name: Experiment name (used as ID slug).
        hypothesis: What you believe to be true.
        rules: List of rules or constraints for this experiment.
        metric: How you'll measure success.
        success_criteria: What "done" looks like.

    Returns a one-line summary suitable for Telegram.
    """
    if not name:
        raise ValueError("Experiment name is required.")

    # Defaults
    experiment_id = name.lower().replace(" ", "-").replace("_", "-")
    hypothesis = hypothesis or f"Testing whether {name} improves outcomes."
    rules = rules or []
    metric = metric or "Outcome quality + velocity."
    success_criteria = success_criteria or f"{name} delivers measurable improvement."

    path = write_experiment(
        name=name,
        hypothesis=hypothesis,
        rules=rules,
        metric=metric,
        success_criteria=success_criteria,
        status="active",
    )
    return f"🧪 Experiment created: *{name}*\nSaved to {path.name}"


def run_experiment_list() -> str:
    """List active experiments from GBrain."""
    from ..gbrain.storage import read_active_experiments

    experiments = read_active_experiments()
    if not experiments:
        return "No active experiments. Create one with /experiment create <name>"

    lines = ["*Active Experiments*"]
    for exp in experiments:
        status = exp.get("status", "active")
        metric = exp.get("metric", "")
        lines.append(f"• {exp.get('name', '?')} [{status}] — {metric}")
    return "\n".join(lines)
