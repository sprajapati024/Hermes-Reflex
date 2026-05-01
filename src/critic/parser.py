"""JSON parsing utilities for the Hermes Reflex critic.

Provides structured parsing of LLM critic output via three strategies:
1. Pydantic model parse (preferred — validates schema)
2. json.loads with schema normalisation
3. Regex extraction as last resort

All strategies raise ParseError on total failure; they never return None.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .decision import VALID_MODES, VALID_RISK_TYPES, VALID_SEVERITIES, CriticDecision


class ParseError(ValueError):
    """Raised when the critic output cannot be parsed into a valid decision."""
    pass


# ---------------------------------------------------------------------------
# Strategy 1 — Pydantic model parse (requires openai >= 1.68)
# ---------------------------------------------------------------------------

def _try_pydantic_parse(raw_text: str) -> CriticDecision | None:
    """Attempt to parse via openai.util.parse_raw_to_model.

    Returns None if openai is not new enough or the content is not parseable.
    """
    try:
        from openai._utils._response_checks import parse_raw_to_model
        from .decision import CriticDecision as CD

        decision = parse_raw_to_model(raw_text.strip(), CD)
        # parse_raw_to_model returns the Pydantic instance; use from_dict
        # to ensure our validation fires
        return CD.from_dict(decision.model_dump())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Strategy 2 — json.loads + normalisation
# ---------------------------------------------------------------------------

def _normalise_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Canonicalise variant key names to the expected schema keys."""
    mapping = {
        # Mode variants
        "response_mode": "mode",
        "responseMode": "mode",
        "decision": "mode",
        # Risk type variants
        "risk": "risk_type",
        "riskType": "risk_type",
        "risk_type ": "risk_type",  # trailing space typo
        # Severity variants
        "severity_level": "severity",
        "impact": "severity",
        # Other variants
        "confidence_score": "confidence",
        "score": "confidence",
        "reason ": "reason",  # trailing space typo
        "reasoning": "reason",
        "explanation": "reason",
        "next_action": "recommended_action",
        "action": "recommended_action",
        "recommended_action ": "recommended_action",  # trailing space
        "override_allowed": "allow_override",
        "can_override": "allow_override",
        "evidence": "evidence_ids",
        "evidence_ids ": "evidence_ids",  # trailing space
    }
    result = {}
    for key, value in data.items():
        canon = mapping.get(key, key)
        result[canon] = value
    return result


def _parse_confidence(value: Any) -> float:
    """Coerce a confidence value to a proper float 0–1."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_list(value: Any) -> list:
    """Coerce a value to a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Could be a JSON array string
        try:
            return json.loads(value)
        except Exception:
            return [value]
    return [value]


def _coerce_and_validate(data: dict[str, Any]) -> CriticDecision:
    """Apply coercion, normalisation, and validation to a raw dict."""
    data = _normalise_keys(data)

    # Coerce types
    data["confidence"] = _parse_confidence(data.get("confidence", 0.0))
    data["evidence_ids"] = _parse_list(data.get("evidence_ids", []))
    data["allow_override"] = bool(data.get("allow_override", True))

    # Clamp confidence
    data["confidence"] = max(0.0, min(1.0, data["confidence"]))

    # Default enum fields if missing
    data.setdefault("mode", "ALLOW")
    data.setdefault("risk_type", "none")
    data.setdefault("severity", "low")
    data.setdefault("reason", "")
    data.setdefault("recommended_action", "")

    # Validate enums — fall back to ALLOW/none/low on bad values
    if data["mode"] not in VALID_MODES:
        data["mode"] = "ALLOW"
    if data["risk_type"] not in VALID_RISK_TYPES:
        data["risk_type"] = "none"
    if data["severity"] not in VALID_SEVERITIES:
        data["severity"] = "low"

    return CriticDecision.from_dict(data)


# ---------------------------------------------------------------------------
# Strategy 3 — Regex extraction (last resort)
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?```",
    re.DOTALL,
)
_TOP_LEVEL_BRACES_RE = re.compile(r"\{.*\}", re.DOTALL)


def _try_regex_extraction(text: str) -> dict[str, Any] | None:
    """Extract JSON from markdown code blocks or top-level braces.

    Returns the parsed dict or None if extraction fails.
    """
    # Try markdown code block first
    m = _JSON_BLOCK_RE.search(text)
    if m:
        content = m.group(1).strip()
    else:
        # Try raw top-level braces
        m = _TOP_LEVEL_BRACES_RE.search(text)
        if not m:
            return None
        content = m.group(0)

    try:
        return json.loads(content)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_critic_response(raw_text: str) -> CriticDecision:
    """Parse the raw LLM output into a CriticDecision.

    Tries three strategies in order:
    1. openai.util.parse_raw_to_model (Pydantic validation)
    2. json.loads + key normalisation + enum coercion
    3. Regex JSON extraction + json.loads + coercion

    Raises:
        ParseError: if all three strategies fail.
    """
    text = raw_text.strip()
    if not text:
        raise ParseError("Empty critic response — cannot parse.")

    # Strategy 1: Pydantic model parse
    decision = _try_pydantic_parse(text)
    if decision is not None:
        return decision

    # Strategy 2: json.loads + normalisation
    try:
        # Try as raw JSON first
        raw = json.loads(text)
        if isinstance(raw, dict):
            return _coerce_and_validate(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 3: Regex extraction + json.loads
    raw = _try_regex_extraction(text)
    if raw is not None and isinstance(raw, dict):
        return _coerce_and_validate(raw)

    raise ParseError(
        f"Critic output could not be parsed as JSON. "
        f"Preview (first 200 chars): {text[:200]!r}"
    )
