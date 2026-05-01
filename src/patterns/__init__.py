"""Hermes Reflex — Patterns package.

Modules:
    rules:    Fast regex/keyword risk detection (rule engine)
    lifecycle: Pattern state transitions (candidate → watching → active → retired)
    detector: Detect patterns in a user message
    evidence: Evidence tracking and promotion threshold checks

Public API:
    from src.patterns.rules import evaluate_rules
    from src.patterns.lifecycle import create_candidate, promote, demote, retire, get_status, get_promotion_advice
    from src.patterns.detector import detect_patterns
    from src.patterns.evidence import get_evidence_summary, count_signals_in_window
"""

from src.patterns.rules import (
    RuleMatch,
    RuleResult,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    evaluate_rules,
)

from src.patterns.lifecycle import (
    create_candidate,
    promote,
    demote,
    retire,
    get_status,
    get_promotion_advice,
)

from src.patterns.detector import detect_patterns

from src.patterns.evidence import (
    get_evidence_summary,
    count_signals_in_window,
)

__all__ = [
    # rules
    "RuleMatch",
    "RuleResult",
    "SEVERITY_HIGH",
    "SEVERITY_MEDIUM",
    "evaluate_rules",
    # lifecycle
    "create_candidate",
    "promote",
    "demote",
    "retire",
    "get_status",
    "get_promotion_advice",
    # detector
    "detect_patterns",
    # evidence
    "get_evidence_summary",
    "count_signals_in_window",
]
