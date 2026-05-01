"""Rule engine for Hermes Reflex — fast regex/keyword risk detection.

This module runs BEFORE the LLM critic. It uses simple pattern matching
to catch obvious risks without any AI involved.

Risk types detected:
  - planning_loop:    Rethinking/replanning instead of executing
  - ui_avoidance:     Adding UI work when user said no UI
  - project_switching: Switching projects instead of finishing current
  - integration_avoidance: Adding integrations instead of core work
  - overbuild_risk:   Feature creep / infrastructure cosplay
  - contract_conflict: Message conflicts with operating contract constraints

Each risk type has:
  - terms:    list of regex patterns (compiled once at import)
  - severity: HIGH → REQUIRE_OVERRIDE, MEDIUM → CHALLENGE
  - response: suggested mode
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# -----------------------------------------------------------------------------
# Data structures
# -----------------------------------------------------------------------------

SEVERITY_HIGH = "HIGH"       # REQUIRE_OVERRIDE
SEVERITY_MEDIUM = "MEDIUM"   # CHALLENGE


@dataclass
class RuleMatch:
    """A single rule that fired."""
    risk_type: str
    matched_term: str
    severity: str
    response_mode: str


@dataclass
class RuleResult:
    """Result of evaluate_rules()."""
    risk_flags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    recommended_mode: str = "ALLOW"
    matched_rules: list[RuleMatch] = field(default_factory=list)
    summary: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "risk_flags": self.risk_flags,
            "confidence": round(self.confidence, 2),
            "recommended_mode": self.recommended_mode,
            "matched_terms": [m.matched_term for m in self.matched_rules],
        }


# -----------------------------------------------------------------------------
# Rule definitions
# -----------------------------------------------------------------------------

# Severity → response mode mapping
_SEVERITY_RESPONSE = {
    SEVERITY_HIGH: "REQUIRE_OVERRIDE",
    SEVERITY_MEDIUM: "CHALLENGE",
}

# Response mode priority (highest wins)
_MODE_PRIORITY = {
    "REQUIRE_OVERRIDE": 4,
    "CHALLENGE": 3,
    "NOTE": 2,
    "ALLOW": 1,
}

# Per-risk-type configuration
_RISK_RULES: dict[str, dict] = {
    "planning_loop": {
        "severity": SEVERITY_MEDIUM,
        "terms": [
            r"\bre(do|write|think|plan)\s+(the\s+)?(prd|spec|roadmap|plan)",
            r"\brethink\s+",
            r"\bpivot\s+again\b",
            r"\bstart\s+from\s+scratch\b",
            r"\bredo\s+the\s+(entire\s+)?(spec PRD|architecture)",
            r"\brewrite\s+(the\s+)?(spec|prd|roadmap)",
            r"\bmore?\s+advanced\b",
            r"\breevaluate\s+the\s+approach\b",
            r"\bgo\s+back\s+to\s+(the\s+)?(drawing\s+board|planning)",
        ],
    },
    "ui_avoidance": {
        "severity": SEVERITY_HIGH,
        "terms": [
            r"\bdashboard\b",
            r"\bfrontend\b",
            r"\bReact\b",
            r"\bVue\b",
            r"\bAngular\b",
            r"\bTailwind\b",
            r"\bUI\s+(polish|update|work)\b",
            r"\bdesign\s+system\b",
            r"\bvisualize\s+",
            r"\bUI\s+layer\b",
            r"\bstylesheet\b",
            r"\bCSS\b",
            r"\blanding\s+page\b",
            r"\bweb\s+interface\b",
            r"\bshow\s+me\s+a\s+(nice\s+)?(UI|interface|dashboard)\b",
        ],
    },
    "project_switching": {
        "severity": SEVERITY_HIGH,
        "terms": [
            r"\bswitch\s+to\s+project\b",
            r"\bwork\s+on\s+(the\s+)?other\s+project\b",
            r"\bcontext\s+switch\b",
            r"\bmeanwhile\s+(on|about)\s+(another|a\s+different)\s+project\b",
            r"\bput\s+.*\s+on\s+hold\b",
            r"\bpause\s+.*\s+and\s+focus\s+on\b",
            r"\bdrop\s+what('s|\s+we('re|\s+are))\s+doing\b",
        ],
    },
    "integration_avoidance": {
        "severity": SEVERITY_MEDIUM,
        "terms": [
            r"\bconnect\s+to\s+",
            r"\badd\s+.*\s+integration\b",
            r"\bwebhook\s+",
            r"\bAPI\s+integration\b",
            r"\bthird[-\s]party\s+",
            r"\bOAuth\b",
            r"\bwebhook\s+handler\b",
            r"\bslack\s+integration\b",
            r"\bdiscord\s+integration\b",
            r"\bZapier\b",
            r"\bMake\.com\b",
            r"\bn8n\b",
        ],
    },
    "overbuild_risk": {
        "severity": SEVERITY_HIGH,
        "terms": [
            r"\bmulti[-\s]?user\b",
            r"\bsaas\b",
            r"\bauth\b(?!\w)",  # "auth" not followed by word char (avoids "auth-experiment")
            r"\bcalendar\s+integration\b",
            r"\bGmail\s+integration\b",
            r"\bemail\s+integration\b",
            r"\banalytics\b",
            r"\bmobile\s+app\b",
            r"\bvector\s+DB\b",
            r"\bvector\s+database\b",
            r"\bwe\s+should\s+add\s+(\w+\s+){0,3}first\b",
            r"\bdo\s+we\s+need\s+a\s+database\b",
            r"\bmaybe\s+we\s+should\s+(add|build|use)\s+\w+\s+for\s+this\b",
            r"\bML\b",
            r"\bmachine\s+learning\b",
            r"\bAI\s+model\b",
            r"\bfine[-\s]?tun(e|ing)\b",
        ],
    },
    "contract_conflict": {
        "severity": SEVERITY_HIGH,
        "terms": [],  # populated dynamically from operating contract
    },
    "experiment_conflict": {
        "severity": SEVERITY_MEDIUM,
        "terms": [],  # populated dynamically from active_experiments
    },
}

# Pre-compile all regex patterns for non-contract rules
for _risk_type, _config in _RISK_RULES.items():
    if _risk_type != "contract_conflict":
        _config["_compiled"] = [
            re.compile(_term, re.IGNORECASE) for _term in _config["terms"]
        ]


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def evaluate_rules(
    user_message: str,
    context: dict | None = None,
) -> RuleResult:
    """Evaluate all rules against a user message.

    Args:
        user_message: The raw user message to evaluate.
        context: Optional context dict with keys:
            - operating_contract: dict with constraint patterns
            - active_experiments: list of experiment names
            - enabled_risks: list of risk types to check (default all)

    Returns:
        RuleResult with risk_flags, confidence, recommended_mode, matched_rules.
    """
    context = context or {}
    result = RuleResult()
    enabled = context.get("enabled_risks", list(_RISK_RULES.keys()))

    # Normalise message for matching
    normalised = _normalise(user_message)

    # Check each risk type
    for risk_type in enabled:
        if risk_type == "contract_conflict":
            _check_contract_conflict(normalised, context, result)
        elif risk_type == "experiment_conflict":
            _check_experiment_conflict(normalised, context, result)
        elif risk_type in _RISK_RULES:
            _check_keyword_rules(risk_type, normalised, result)

    # Compute overall recommended mode (most severe wins)
    result.recommended_mode = _resolve_mode(result.matched_rules)

    # Confidence: based on number and severity of matches
    result.confidence = _compute_confidence(result.matched_rules)

    return result


def _check_keyword_rules(risk_type: str, text: str, result: RuleResult) -> None:
    config = _RISK_RULES[risk_type]
    severity = config["severity"]
    response = _SEVERITY_RESPONSE[severity]

    for compiled in config.get("_compiled", []):
        m = compiled.search(text)
        if m:
            matched = m.group(0)
            result.risk_flags.append(risk_type)
            result.matched_rules.append(RuleMatch(
                risk_type=risk_type,
                matched_term=matched,
                severity=severity,
                response_mode=response,
            ))
            break  # one match per risk type is enough

    # Update recommended_mode so direct callers get a meaningful value
    if result.matched_rules:
        result.recommended_mode = _resolve_mode(result.matched_rules)


def _check_contract_conflict(text: str, context: dict, result: RuleResult) -> None:
    contract = context.get("operating_contract")
    if not contract:
        return

    constraints = contract.get("constraints", {})
    severity = SEVERITY_HIGH
    response = _SEVERITY_RESPONSE[severity]

    # The storage-backed OperatingContract returns constraints as a simple
    # list[str] (e.g. ["No dashboard", "No frontend"]). Older tests and
    # hand-authored contexts may provide the richer dict form:
    # {"constraint-id": {"conflict_patterns": [...]}}. Support both shapes
    # here so the middleware can pass load_contract().to_dict() directly.
    if isinstance(constraints, list):
        for constraint in constraints:
            if not isinstance(constraint, str):
                continue
            patterns = _patterns_from_constraint_text(constraint)
            for pattern in patterns:
                try:
                    if re.search(pattern, text, re.IGNORECASE):
                        result.risk_flags.append("contract_conflict")
                        result.matched_rules.append(RuleMatch(
                            risk_type="contract_conflict",
                            matched_term=f"[{constraint}] {pattern}",
                            severity=severity,
                            response_mode=response,
                        ))
                        result.recommended_mode = _resolve_mode(result.matched_rules)
                        return
                except re.error:
                    continue
        return

    # Check each constraint's conflict patterns against the message
    for constraint_id, constraint in constraints.items():
        patterns = constraint.get("conflict_patterns", [])
        for pattern in patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    result.risk_flags.append("contract_conflict")
                    result.matched_rules.append(RuleMatch(
                        risk_type="contract_conflict",
                        matched_term=f"[{constraint_id}] {pattern}",
                        severity=severity,
                        response_mode=response,
                    ))
                    # Update recommended_mode so direct callers get a meaningful value
                    result.recommended_mode = _resolve_mode(result.matched_rules)
                    return  # one contract conflict is enough
            except re.error:
                pass  # skip invalid patterns


def _patterns_from_constraint_text(constraint: str) -> list[str]:
    """Return conservative conflict regexes for a plain-text constraint.

    Storage-backed contracts currently store constraints as human-readable
    strings. For "No X" constraints, the conflicting user message usually
    mentions X ("dashboard"), not the full phrase ("No dashboard").
    """
    clean = constraint.strip()
    if not clean:
        return []

    patterns = [re.escape(clean)]

    lower = clean.lower()
    if lower.startswith("no "):
        forbidden = clean[3:].strip()
        if forbidden:
            patterns.append(rf"\b{re.escape(forbidden)}\b")

    # Common Hermes Reflex operating-contract constraints that are phrased
    # as policy rather than a simple "No X" ban.
    if lower == "telegram commands only":
        patterns.extend([
            r"\bweb\s*interface\b",
            r"\bweb\s*ui\b",
            r"\bbrowser\s*plugin\b",
            r"\bbrowser\s*extension\b",
            r"\bchrome\s*extension\b",
        ])

    return patterns


def _check_experiment_conflict(text: str, context: dict, result: RuleResult) -> None:
    experiments = context.get("active_experiments", [])
    if not experiments:
        return

    severity = SEVERITY_MEDIUM
    response = _SEVERITY_RESPONSE[severity]

    for name in experiments:
        # Check if user is talking about ending the experiment early
        for pattern in [
            rf"\bstop\b.*{re.escape(name)}",
            rf"\bcancel\b.*{re.escape(name)}",
            rf"\babort\b.*{re.escape(name)}",
            rf"\bend\s+(the\s+)?experiment\b",
            rf"\bkill\s+(the\s+)?(experiment|run)\b",
        ]:
            if re.search(pattern, text, re.IGNORECASE):
                result.risk_flags.append("experiment_conflict")
                result.matched_rules.append(RuleMatch(
                    risk_type="experiment_conflict",
                    matched_term=name,
                    severity=severity,
                    response_mode=response,
                ))
                result.recommended_mode = _resolve_mode(result.matched_rules)
                return


def _resolve_mode(matches: list[RuleMatch]) -> str:
    """Pick the most severe response mode from matched rules."""
    if not matches:
        return "ALLOW"
    return max(matches, key=lambda m: _MODE_PRIORITY.get(m.response_mode, 0)).response_mode


def _compute_confidence(matches: list[RuleMatch]) -> float:
    """Compute confidence 0.0–1.0 based on match severity and count."""
    if not matches:
        return 0.0
    high = sum(1 for m in matches if m.severity == SEVERITY_HIGH)
    medium = sum(1 for m in matches if m.severity == SEVERITY_MEDIUM)
    total = len(matches)
    # 1 high = 0.75, 2+ high = 0.90; medium adds 0.25 each
    score = 0.6 + (high * 0.15) + (medium * 0.08)
    return min(score, 0.98)


def _normalise(text: str) -> str:
    """Normalise text for consistent matching."""
    return text.lower().strip()
