"""Rule engine for Hermes Reflex — fast regex/keyword risk detection.

This module runs BEFORE the LLM critic. It uses simple pattern matching
to catch obvious risks without any AI involved.

Built-in risk types:
  - planning_loop:         Rethinking/replanning instead of executing
  - ui_avoidance:          Adding UI work when user said no UI
  - project_switching:     Switching projects instead of finishing current
  - integration_avoidance: Adding integrations instead of core work
  - overbuild_risk:        Feature creep / infrastructure cosplay
  - contract_conflict:     Conflicts with operating contract constraints
  - experiment_conflict:   Requests to end active experiments early

YAML rules:
  Additional rules are loaded from the directory specified by
  HERMES_REFLEX_RULES_DIR (default: ~/gbrain/reflex/rules).
  YAML rules are merged with built-ins; same-ID YAML rules override built-ins.
  Falls back gracefully if the directory is missing or unreadable.

Each rule has:
  - terms:    list of regex patterns (compiled once at load)
  - severity: HIGH → REQUIRE_OVERRIDE, MEDIUM → CHALLENGE
  - response: suggested mode
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

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
# YAML rule loading
# -----------------------------------------------------------------------------

def _compile_yaml_term(term: str) -> Optional[re.Pattern]:
    """Compile a YAML rule term as a regex.

    Plain words (no regex metacharacters) are wrapped in word boundaries.
    Terms that already look like patterns are used as-is.
    """
    has_meta = bool(re.search(r'[\\|()\[\]{}^$*+?]', term))
    pattern = term if has_meta else rf'\b{re.escape(term)}\b'
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error:
        return None


def load_yaml_rules(rules_dir: Optional[str] = None) -> dict[str, dict]:
    """Load rule definitions from YAML files.

    Args:
        rules_dir: Directory to load from.  If None, reads
                   HERMES_REFLEX_RULES_DIR env var, then falls back to
                   ~/gbrain/reflex/rules.

    Returns:
        dict mapping rule_id → rule config dict (same shape as _RISK_RULES).
        Empty dict if the directory is missing or unreadable.
    """
    if rules_dir is None:
        rules_dir = os.environ.get(
            "HERMES_REFLEX_RULES_DIR",
            os.path.expanduser("~/gbrain/reflex/rules"),
        )

    if not os.path.isdir(rules_dir):
        return {}

    try:
        import yaml
    except ImportError:
        log.warning("[Reflex] pyyaml not installed — YAML rules disabled")
        return {}

    loaded: dict[str, dict] = {}
    for filename in sorted(os.listdir(rules_dir)):
        if not (filename.endswith(".yaml") or filename.endswith(".yml")):
            continue
        filepath = os.path.join(rules_dir, filename)
        try:
            with open(filepath, encoding="utf-8") as fh:
                rule = yaml.safe_load(fh)
            if not isinstance(rule, dict):
                continue
            if not rule.get("enabled", True):
                continue

            rule_id = str(rule.get("id") or filename.replace(".yaml", "").replace(".yml", ""))
            severity_raw = str(rule.get("severity", "medium")).upper()
            severity = SEVERITY_HIGH if severity_raw == "HIGH" else SEVERITY_MEDIUM
            terms = [str(t) for t in (rule.get("terms") or [])]
            compiled = [c for t in terms if (c := _compile_yaml_term(t)) is not None]

            # Explicit mode override: lets YAML rules specify NOTE, CLARIFY,
            # etc. without being constrained to the HIGH→REQUIRE_OVERRIDE /
            # MEDIUM→CHALLENGE severity mapping.
            mode_raw = str(rule.get("mode") or "").strip().upper()
            mode_override: Optional[str] = mode_raw if mode_raw else None

            loaded[rule_id] = {
                "severity": severity,
                "terms": terms,
                "_compiled": compiled,
                "_from_yaml": True,
                "mode_override": mode_override,
                "requires_evidence": bool(rule.get("requires_evidence", False)),
                "cooldown_hours": int(rule.get("cooldown_hours", 0)),
            }
        except Exception as exc:
            log.warning("[Reflex] failed to load YAML rule %s: %s", filename, exc)

    return loaded


def _build_active_rules() -> dict[str, dict]:
    """Merge built-in rules with YAML overrides. YAML wins on ID collision."""
    yaml_rules = {}
    try:
        yaml_rules = load_yaml_rules()
    except Exception as exc:
        log.warning("[Reflex] YAML rule load failed: %s", exc)
    return {**_RISK_RULES, **yaml_rules}


# Active rules: built-ins + any YAML overrides loaded at import time.
# Call _build_active_rules() again if you need to hot-reload after startup.
_ACTIVE_RULES: dict[str, dict] = _build_active_rules()


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def evaluate_rules(
    user_message: str,
    context: dict | None = None,
) -> RuleResult:
    """Evaluate all rules against a user message.

    Checks built-in rules plus any YAML rules loaded at startup.

    Args:
        user_message: The raw user message to evaluate.
        context: Optional context dict with keys:
            - operating_contract: dict with constraint patterns
            - active_experiments: list of experiment names
            - enabled_risks: list of risk types to check (default: all active)

    Returns:
        RuleResult with risk_flags, confidence, recommended_mode, matched_rules.
    """
    context = context or {}
    result = RuleResult()
    enabled = context.get("enabled_risks", list(_ACTIVE_RULES.keys()))

    # Normalise message for matching
    normalised = _normalise(user_message)

    # Check each risk type
    for risk_type in enabled:
        if risk_type == "contract_conflict":
            _check_contract_conflict(normalised, context, result)
        elif risk_type == "experiment_conflict":
            _check_experiment_conflict(normalised, context, result)
        elif risk_type in _ACTIVE_RULES:
            _check_keyword_rules(risk_type, normalised, result)

    # Compute overall recommended mode (most severe wins)
    result.recommended_mode = _resolve_mode(result.matched_rules)

    # Confidence: based on number and severity of matches
    result.confidence = _compute_confidence(result.matched_rules)

    return result


def _check_keyword_rules(risk_type: str, text: str, result: RuleResult) -> None:
    config = _ACTIVE_RULES[risk_type]
    severity = config["severity"]
    # YAML rules may carry an explicit mode_override (e.g. NOTE, CLARIFY).
    # Fall back to the severity→mode mapping for built-in rules.
    response = config.get("mode_override") or _SEVERITY_RESPONSE[severity]

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
