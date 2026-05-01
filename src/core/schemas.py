"""Core data schemas for Hermes Reflex middleware.

Provides:
- ReflexContext: everything the middleware needs to process a message
- ReflexResult: everything Hermes needs to produce its response
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ReflexContext:
    """All input data required to process one reflex pass.

    Attributes:
        user_message: The raw incoming Telegram message text.
        project: Optional project name to scope evidence retrieval.
        include_reflex_instructions: Whether to include Reflex instructions in Hermes output.
        enabled: Whether Reflex is globally enabled.
    """
    user_message: str
    project: Optional[str] = None
    include_reflex_instructions: bool = True
    enabled: bool = True

    # Populated by middleware stages
    rule_result: dict[str, Any] = field(default_factory=dict)
    contract_conflict: dict[str, Any] = field(default_factory=dict)
    active_experiments: list[dict[str, Any]] = field(default_factory=list)
    retrieved_evidence: list[dict[str, Any]] = field(default_factory=list)
    recent_patterns: list[dict[str, Any]] = field(default_factory=list)
    pause_state: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReflexResult:
    """The output of one reflex pass.

    This is what the middleware returns — Hermes consumes it to decide
    how to frame its response.

    Attributes:
        mode: The response mode (ALLOW, NOTE, CHALLENGE, etc.)
        risk_type: The type of risk detected (if any)
        confidence: How confident the critic was (0.0–1.0)
        severity: low / medium / high
        hermes_instruction: The instruction string for Hermes
        evidence: The evidence used to justify the decision
        decision_id: GBrain decision file ID
        mode_raw: Raw critic decision dict (for debugging/logging)
    """
    mode: str
    risk_type: str
    confidence: float
    severity: str
    hermes_instruction: str
    evidence: list[dict[str, Any]]
    decision_id: Optional[str] = None
    mode_raw: dict[str, Any] = field(default_factory=dict)

    # Computed — not passed in, derived in __post_init__
    _is_challenge: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._is_challenge = self.mode in (
            "CHALLENGE",
            "REQUIRE_OVERRIDE",
            "NOTE",
            "CLARIFY",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "risk_type": self.risk_type,
            "confidence": round(self.confidence, 3),
            "severity": self.severity,
            "hermes_instruction": self.hermes_instruction,
            "evidence": self.evidence,
            "decision_id": self.decision_id,
            "is_challenge": self._is_challenge,
        }
