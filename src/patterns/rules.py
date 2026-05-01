"""Pattern rules for Hermes Reflex — fast regex/keyword risk detection.

This module exposes `evaluate_rules()` for the reflex middleware.
Rules are defined in `src.core.rule_engine`.

Risk types:
    planning_loop       — Rethinking/replanning instead of executing
    ui_avoidance        — Adding UI work when user said no UI
    project_switching   — Switching projects instead of finishing current
    integration_avoidance — Adding integrations instead of core work
    overbuild_risk      — Feature creep / infrastructure cosplay
    contract_conflict   — Message conflicts with operating contract constraints
    experiment_conflict — User wants to stop/abort an active experiment

Usage:
    from src.patterns.rules import evaluate_rules

    result = evaluate_rules(
        "Should we add a dashboard?",
        context={
            "operating_contract": {"constraints": {...}},
            "active_experiments": ["auth-test"],
        }
    )
    if result.risk_flags:
        print(f"Risks: {result.risk_flags}, mode: {result.recommended_mode}")
"""

from src.core.rule_engine import (
    RuleMatch,
    RuleResult,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    evaluate_rules,
)

__all__ = [
    "RuleMatch",
    "RuleResult",
    "SEVERITY_HIGH",
    "SEVERITY_MEDIUM",
    "evaluate_rules",
]
