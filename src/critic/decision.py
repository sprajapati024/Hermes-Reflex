"""Critic decision dataclass for Hermes Reflex.

Defines the structured output schema for the LLM critic layer.
All fields are required except evidence_ids (which may be empty).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResponseMode(str, Enum):
    """Response mode classifications."""
    ALLOW = "ALLOW"
    NOTE = "NOTE"
    CHALLENGE = "CHALLENGE"
    CLARIFY = "CLARIFY"
    REQUIRE_OVERRIDE = "REQUIRE_OVERRIDE"
    SILENT_LOG = "SILENT_LOG"


class RiskType(str, Enum):
    """Risk type taxonomy."""
    NONE = "none"
    PLANNING_LOOP = "planning_loop"
    UI_AVOIDANCE = "ui_avoidance"
    PROJECT_SWITCHING = "project_switching"
    INTEGRATION_AVOIDANCE = "integration_avoidance"
    OVERBUILD_RISK = "overbuild_risk"
    CONTRACT_CONFLICT = "contract_conflict"
    OTHER = "other"


class Severity(str, Enum):
    """Severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


VALID_MODES = {m.value for m in ResponseMode}
VALID_RISK_TYPES = {r.value for r in RiskType}
VALID_SEVERITIES = {s.value for s in Severity}


@dataclass
class CriticDecision:
    """Structured output from the LLM critic.

    Attributes:
        mode: Classification response mode.
        risk_type: The type of risk detected.
        confidence: How confident the critic is (0.0–1.0).
        severity: Low / medium / high.
        evidence_ids: List of evidence IDs supporting this decision.
        reason: Short factual explanation.
        recommended_action: One concrete next action (imperative).
        allow_override: Whether the user may override this decision.
    """
    mode: str
    risk_type: str
    confidence: float
    severity: str
    evidence_ids: list[str] = field(default_factory=list)
    reason: str = ""
    recommended_action: str = ""
    allow_override: bool = True

    # Internal only — not part of the JSON schema
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """Validate enum fields after construction."""
        if self.mode not in VALID_MODES:
            raise ValueError(
                f"Invalid mode {self.mode!r}. Must be one of: {sorted(VALID_MODES)}"
            )
        if self.risk_type not in VALID_RISK_TYPES:
            raise ValueError(
                f"Invalid risk_type {self.risk_type!r}. "
                f"Must be one of: {sorted(VALID_RISK_TYPES)}"
            )
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity {self.severity!r}. "
                f"Must be one of: {sorted(VALID_SEVERITIES)}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence {self.confidence} must be between 0.0 and 1.0"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict matching the critic JSON schema."""
        return {
            "mode": self.mode,
            "risk_type": self.risk_type,
            "confidence": round(self.confidence, 3),
            "severity": self.severity,
            "evidence_ids": self.evidence_ids,
            "reason": self.reason,
            "recommended_action": self.recommended_action,
            "allow_override": self.allow_override,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CriticDecision":
        """Construct a CriticDecision from a dict (e.g. parsed JSON).

        Normalises top-level keys and validates enum fields.
        Unknown keys are accepted and stored in _raw.
        """
        # Normalise underscore/dash variants
        normalised = {
            "mode": data.get("mode", "ALLOW"),
            "risk_type": data.get("risk_type", "none"),
            "confidence": float(data.get("confidence", 0.0)),
            "severity": data.get("severity", "low"),
            "evidence_ids": data.get("evidence_ids") or [],
            "reason": data.get("reason", ""),
            "recommended_action": data.get("recommended_action", ""),
            "allow_override": bool(data.get("allow_override", True)),
        }

        # Capture any extra keys so nothing is silently dropped
        known = set(normalised)
        raw = {k: v for k, v in data.items() if k not in known}

        return cls(**normalised, _raw=raw)

    @classmethod
    def default_allow(cls) -> "CriticDecision":
        """Return a safe default when the critic cannot be reached."""
        return cls(
            mode="ALLOW",
            risk_type="none",
            confidence=0.0,
            severity="low",
            evidence_ids=[],
            reason="Critic unavailable — defaulting to ALLOW.",
            recommended_action="Respond normally.",
            allow_override=True,
            _raw={},
        )
