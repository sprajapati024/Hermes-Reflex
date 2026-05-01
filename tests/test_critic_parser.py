"""Tests for src/critic/parser.py."""

from __future__ import annotations

import pytest

from src.critic.parser import (
    ParseError,
    _coerce_and_validate,
    _normalise_keys,
    _parse_confidence,
    _parse_list,
    _try_pydantic_parse,
    _try_regex_extraction,
    parse_critic_response,
)
from src.critic.decision import CriticDecision


# ---------------------------------------------------------------------------
# _normalise_keys
# ---------------------------------------------------------------------------

def test_normalise_keys_no_change():
    data = {"mode": "CHALLENGE", "risk_type": "ui_avoidance", "confidence": 0.8}
    result = _normalise_keys(data)
    assert result == data


def test_normalise_keys_response_mode_variant():
    data = {"response_mode": "NOTE", "risk_type": "planning_loop", "confidence": 0.5}
    result = _normalise_keys(data)
    assert result["mode"] == "NOTE"
    assert "response_mode" not in result


def test_normalise_keys_score_variant():
    data = {"score": 0.75, "mode": "ALLOW", "risk_type": "none"}
    result = _normalise_keys(data)
    assert result["confidence"] == 0.75


def test_normalise_keys_reasoning_variant():
    data = {"reasoning": "Too early for analytics", "mode": "ALLOW", "risk_type": "none", "confidence": 0.0}
    result = _normalise_keys(data)
    assert result["reason"] == "Too early for analytics"


# ---------------------------------------------------------------------------
# _parse_confidence
# ---------------------------------------------------------------------------

def test_parse_confidence_float():
    assert _parse_confidence(0.85) == 0.85


def test_parse_confidence_int():
    assert _parse_confidence(1) == 1.0


def test_parse_confidence_string():
    assert _parse_confidence("0.7") == 0.7


def test_parse_confidence_invalid():
    assert _parse_confidence("junk") == 0.0
    assert _parse_confidence(None) == 0.0


# ---------------------------------------------------------------------------
# _parse_list
# ---------------------------------------------------------------------------

def test_parse_list_already_list():
    assert _parse_list([1, 2, 3]) == [1, 2, 3]


def test_parse_list_none():
    assert _parse_list(None) == []


def test_parse_list_string_json():
    assert _parse_list('["a", "b"]') == ["a", "b"]


def test_parse_list_single_string():
    assert _parse_list("hello") == ["hello"]


# ---------------------------------------------------------------------------
# _coerce_and_validate — enum coercion
# ---------------------------------------------------------------------------

def test_coerce_unknown_mode_defaults_to_allow():
    data = {"mode": "NOT_A_REAL_MODE", "risk_type": "none", "confidence": 0.5, "severity": "low"}
    result = _coerce_and_validate(data)
    assert result.mode == "ALLOW"


def test_coerce_unknown_risk_type_defaults_to_none():
    data = {"mode": "ALLOW", "risk_type": "garbage", "confidence": 0.5, "severity": "low"}
    result = _coerce_and_validate(data)
    assert result.risk_type == "none"


def test_coerce_unknown_severity_defaults_to_low():
    data = {"mode": "ALLOW", "risk_type": "none", "confidence": 0.5, "severity": "crazy"}
    result = _coerce_and_validate(data)
    assert result.severity == "low"


def test_coerce_confidence_clamps_high():
    data = {"mode": "ALLOW", "risk_type": "none", "confidence": 1.5, "severity": "low"}
    result = _coerce_and_validate(data)
    assert result.confidence == 1.0


def test_coerce_confidence_clamps_negative():
    data = {"mode": "ALLOW", "risk_type": "none", "confidence": -0.5, "severity": "low"}
    result = _coerce_and_validate(data)
    assert result.confidence == 0.0


def test_coerce_missing_fields_get_defaults():
    # Only mode + risk_type provided — rest should default
    data = {"mode": "CHALLENGE", "risk_type": "ui_avoidance"}
    result = _coerce_and_validate(data)
    assert result.confidence == 0.0
    assert result.severity == "low"
    assert result.evidence_ids == []
    assert result.allow_override is True


# ---------------------------------------------------------------------------
# _try_regex_extraction
# ---------------------------------------------------------------------------

def test_regex_extracts_json_block():
    text = '```json\n{"mode": "CHALLENGE", "risk_type": "ui_avoidance"}\n```'
    result = _try_regex_extraction(text)
    assert result is not None
    assert result["mode"] == "CHALLENGE"


def test_regex_extracts_raw_braces():
    text = 'Here is my response: {"mode": "ALLOW", "risk_type": "none"}\nThanks!'
    result = _try_regex_extraction(text)
    assert result is not None
    assert result["mode"] == "ALLOW"


def test_regex_returns_none_for_non_json():
    text = "This is not JSON at all, just plain text."
    result = _try_regex_extraction(text)
    assert result is None


# ---------------------------------------------------------------------------
# parse_critic_response — integration of all strategies
# ---------------------------------------------------------------------------

def test_parse_valid_minimal_json():
    raw = '{"mode": "ALLOW", "risk_type": "none", "confidence": 0.0, "severity": "low"}'
    result = parse_critic_response(raw)
    assert isinstance(result, CriticDecision)
    assert result.mode == "ALLOW"


def test_parse_full_valid_json():
    raw = (
        '{"mode": "CHALLENGE", "risk_type": "ui_avoidance", "confidence": 0.86, '
        '"severity": "medium", "evidence_ids": ["exp_no_dashboard"], '
        '"reason": "Conflicts with no-dashboard constraint.", '
        '"recommended_action": "Ship /patterns first.", '
        '"allow_override": true}'
    )
    result = parse_critic_response(raw)
    assert result.mode == "CHALLENGE"
    assert result.risk_type == "ui_avoidance"
    assert result.confidence == 0.86
    assert result.severity == "medium"
    assert result.evidence_ids == ["exp_no_dashboard"]
    assert result.allow_override is True


def test_parse_empty_response_raises():
    with pytest.raises(ParseError):
        parse_critic_response("")


def test_parse_prose_only_raises():
    with pytest.raises(ParseError):
        parse_critic_response("I think this looks fine, let me help you with that.")


def test_parse_json_in_markdown_block():
    raw = '```json\n{"mode": "REQUIRE_OVERRIDE", "risk_type": "contract_conflict", "confidence": 0.9, "severity": "high"}\n```'
    result = parse_critic_response(raw)
    assert result.mode == "REQUIRE_OVERRIDE"
    assert result.risk_type == "contract_conflict"


def test_parse_variant_keys_normalised():
    raw = '{"response_mode": "NOTE", "risk": "planning_loop", "confidence_score": 0.7, "severity": "low"}'
    result = parse_critic_response(raw)
    assert result.mode == "NOTE"
    assert result.risk_type == "planning_loop"
    assert result.confidence == 0.7


def test_parse_extra_keys_ignored():
    raw = '{"mode": "ALLOW", "risk_type": "none", "confidence": 0.0, "severity": "low", "extra_field": 123}'
    result = parse_critic_response(raw)
    assert result.mode == "ALLOW"
    assert result._raw.get("extra_field") == 123


# ---------------------------------------------------------------------------
# CriticDecision round-trip
# ---------------------------------------------------------------------------

def test_critic_decision_to_dict_round_trip():
    original = CriticDecision(
        mode="CHALLENGE",
        risk_type="ui_avoidance",
        confidence=0.86,
        severity="medium",
        evidence_ids=["exp_no_dashboard", "pattern_ui_avoidance"],
        reason="Conflicts with the no-dashboard constraint.",
        recommended_action="Ship /patterns before dashboard work.",
        allow_override=True,
    )
    data = original.to_dict()
    restored = CriticDecision.from_dict(data)
    assert restored.mode == original.mode
    assert restored.risk_type == original.risk_type
    assert restored.confidence == original.confidence
    assert restored.severity == original.severity
    assert restored.evidence_ids == original.evidence_ids
    assert restored.reason == original.reason
    assert restored.recommended_action == original.recommended_action
    assert restored.allow_override == original.allow_override


def test_critic_decision_default_allow():
    decision = CriticDecision.default_allow()
    assert decision.mode == "ALLOW"
    assert decision.risk_type == "none"
    assert decision.confidence == 0.0
    assert "Critic unavailable" in decision.reason


def test_critic_decision_validation_raises_bad_mode():
    with pytest.raises(ValueError, match="Invalid mode"):
        CriticDecision(
            mode="BANANA",
            risk_type="none",
            confidence=0.0,
            severity="low",
        )


def test_critic_decision_validation_raises_bad_confidence():
    with pytest.raises(ValueError, match="confidence"):
        CriticDecision(
            mode="ALLOW",
            risk_type="none",
            confidence=1.5,
            severity="low",
        )
