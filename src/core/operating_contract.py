"""Operating contract management for Hermes Reflex.

The operating contract defines:
- Active goal: what we're trying to achieve right now
- Constraints: hard limits Reflex must enforce
- Reflex Authority: what Reflex is allowed to do
- Override Policy: how users can override Reflex decisions

This module provides:
- ensure_default_contract(): create contract file if missing
- load_contract(): read and parse the current contract
- check_contract_conflict(): detect if a user message conflicts with active constraints
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..gbrain.paths import get_current_contract_path
from ..gbrain.storage import read_current_contract, write_operating_contract

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

DEFAULT_CONSTRAINTS = [
    "No dashboard",
    "No frontend",
    "Telegram commands only",
    "GBrain markdown storage",
    "Use OpenAI text-embedding-3-small for retrieval",
    "No new integrations before core commands work",
]

CONFLICT_TERMS: dict[str, list[str]] = {
    "No dashboard": [
        r"\bdashboard\b",
        r"\bdash board\b",
        r"visualize patterns",
        r"pattern visualiz",
        r"pattern dashboard",
    ],
    "No frontend": [
        r"\bfrontend\b",
        r"\bfront-end\b",
        r"\bReact\b",
        r"\bTailwind\b",
        r"\bui\b.*polish\b",
        r"\bdesign system\b",
        r"\bUI\b",
        r"\bvisualiz",
    ],
    "Telegram commands only": [
        r"\bweb\s*interface\b",
        r"\bweb\s*ui\b",
        r"\bbrowser\s*plugin\b",
        r"\bbrowser\s*extension\b",
        r"\bchrome\s*extension\b",
    ],
    "No new integrations before core commands work": [
        r"\bGmail\s+integration\b",
        r"\bGoogle\s+calendar\b",
        r"\bcalendly\b",
        r"\bLinear\s+integration\b",
        r"\bNotion\s+sync\b",
        r"\bSlack\s+bot\b",
        r"\bDiscord\s+bot\b",
    ],
}

# Severity mapping: which constraints get which severity when matched
CONSTRAINT_SEVERITY: dict[str, str] = {
    "No dashboard": "high",
    "No frontend": "high",
    "Telegram commands only": "medium",
    "No new integrations before core commands work": "medium",
}


@dataclass
class ContractConflict:
    conflict: bool
    constraint: Optional[str] = None
    confidence: float = 0.0
    recommended_mode: str = "ALLOW"
    matched_term: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict": self.conflict,
            "constraint": self.constraint,
            "confidence": self.confidence,
            "recommended_mode": self.recommended_mode,
            "matched_term": self.matched_term,
        }


@dataclass
class OperatingContract:
    active_goal: str
    constraints: list[str]
    reflex_authority: str
    override_policy: str
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_storage(cls) -> "OperatingContract":
        """Load the current operating contract from GBrain storage."""
        data, _ = read_current_contract()
        return cls(
            active_goal=data.get("active_goal", ""),
            constraints=data.get("constraints", []),
            reflex_authority=data.get("reflex_authority", ""),
            override_policy=data.get("override_policy", ""),
            raw=data,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OperatingContract":
        return cls(
            active_goal=data.get("active_goal", ""),
            constraints=data.get("constraints", []),
            reflex_authority=data.get("reflex_authority", ""),
            override_policy=data.get("override_policy", ""),
            raw=data,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_goal": self.active_goal,
            "constraints": self.constraints,
            "reflex_authority": self.reflex_authority,
            "override_policy": self.override_policy,
        }


# ---------------------------------------------------------------------------
# Contract lifecycle
# ---------------------------------------------------------------------------

def ensure_default_contract() -> OperatingContract:
    """Create the default operating contract if it doesn't exist.

    Returns the loaded contract.
    """
    path = get_current_contract_path()
    if path.exists():
        return OperatingContract.from_storage()

    write_operating_contract(
        active_goal="Ship Hermes Reflex v1",
        constraints=DEFAULT_CONSTRAINTS,
        reflex_authority="Hermes Reflex may challenge requests that conflict with this contract.",
        override_policy="The user can override, but overrides must be logged.",
    )
    return OperatingContract.from_storage()


def load_contract() -> OperatingContract:
    """Load the current operating contract, creating default if missing."""
    return ensure_default_contract()


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def check_contract_conflict(
    user_message: str,
    contract: Optional[OperatingContract] = None,
) -> ContractConflict:
    """Check if a user message conflicts with active contract constraints.

    Args:
        user_message: The raw user message to check.
        contract: The operating contract to check against. If None, loads current.

    Returns:
        ContractConflict with conflict=True if a constraint was violated.
    """
    if contract is None:
        contract = load_contract()

    msg_lower = user_message.lower()

    for constraint in contract.constraints:
        # Check for exact constraint phrase
        if constraint.lower() in msg_lower:
            return ContractConflict(
                conflict=True,
                constraint=constraint,
                confidence=0.95,
                recommended_mode="REQUIRE_OVERRIDE",
                matched_term=constraint,
            )

        # Check for known conflict terms
        if constraint in CONFLICT_TERMS:
            for pattern in CONFLICT_TERMS[constraint]:
                if re.search(pattern, msg_lower, re.IGNORECASE):
                    severity = CONSTRAINT_SEVERITY.get(constraint, "medium")
                    mode = (
                        "REQUIRE_OVERRIDE"
                        if severity == "high"
                        else "CHALLENGE"
                    )
                    return ContractConflict(
                        conflict=True,
                        constraint=constraint,
                        confidence=0.85,
                        recommended_mode=mode,
                        matched_term=pattern,
                    )

    return ContractConflict(conflict=False)
