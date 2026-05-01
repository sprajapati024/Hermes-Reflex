"""Hermes Reflex — Patterns package.

Modules:
    rules: Fast regex/keyword risk detection (rule engine)

Public API:
    from src.patterns.rules import evaluate_rules
"""

from src.patterns.rules import (
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
