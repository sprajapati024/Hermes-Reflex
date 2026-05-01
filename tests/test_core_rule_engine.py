"""Tests for src/core/rule_engine.py."""

from __future__ import annotations

import pytest

from src.core.rule_engine import (
    RuleMatch,
    RuleResult,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    _check_contract_conflict,
    _check_experiment_conflict,
    _check_keyword_rules,
    _compute_confidence,
    _normalise,
    _resolve_mode,
    evaluate_rules,
)


# ---------------------------------------------------------------------------
# _normalise
# ---------------------------------------------------------------------------

def test_normalise_lowers_and_strips():
    assert _normalise("  HELLO World  ") == "hello world"


# ---------------------------------------------------------------------------
# _resolve_mode
# ---------------------------------------------------------------------------

def test_resolve_mode_no_matches_returns_allow():
    assert _resolve_mode([]) == "ALLOW"


def test_resolve_mode_high_wins():
    matches = [
        RuleMatch("ui_avoidance", "dashboard", SEVERITY_MEDIUM, "CHALLENGE"),
        RuleMatch("overbuild_risk", "multi-user", SEVERITY_HIGH, "REQUIRE_OVERRIDE"),
    ]
    assert _resolve_mode(matches) == "REQUIRE_OVERRIDE"


def test_resolve_mode_challenge_wins_over_allow():
    matches = [
        RuleMatch("planning_loop", "redo PRD", SEVERITY_MEDIUM, "CHALLENGE"),
    ]
    assert _resolve_mode(matches) == "CHALLENGE"


# ---------------------------------------------------------------------------
# _compute_confidence
# ---------------------------------------------------------------------------

def test_confidence_no_matches():
    assert _compute_confidence([]) == 0.0


def test_confidence_single_medium_match():
    matches = [RuleMatch("planning_loop", "redo PRD", SEVERITY_MEDIUM, "CHALLENGE")]
    conf = _compute_confidence(matches)
    assert 0.6 < conf < 0.8


def test_confidence_high_match():
    matches = [RuleMatch("overbuild_risk", "multi-user", SEVERITY_HIGH, "REQUIRE_OVERRIDE")]
    conf = _compute_confidence(matches)
    assert conf >= 0.75


def test_confidence_multiple_high_matches():
    matches = [
        RuleMatch("overbuild_risk", "multi-user", SEVERITY_HIGH, "REQUIRE_OVERRIDE"),
        RuleMatch("ui_avoidance", "dashboard", SEVERITY_HIGH, "REQUIRE_OVERRIDE"),
    ]
    conf = _compute_confidence(matches)
    assert conf >= 0.89  # 0.6 + 2*0.15 = 0.90; avoid exact-float comparison


def test_confidence_caps_at_098():
    matches = [
        RuleMatch("overbuild_risk", "multi-user", SEVERITY_HIGH, "REQUIRE_OVERRIDE"),
        RuleMatch("ui_avoidance", "dashboard", SEVERITY_HIGH, "REQUIRE_OVERRIDE"),
        RuleMatch("planning_loop", "redo PRD", SEVERITY_MEDIUM, "CHALLENGE"),
    ]
    assert _compute_confidence(matches) <= 0.98
    assert _compute_confidence(matches) > 0.9  # definitely above no-match baseline


# ---------------------------------------------------------------------------
# _check_keyword_rules
# ---------------------------------------------------------------------------

def test_check_keyword_rules_planning_loop():
    result = RuleResult()
    _check_keyword_rules("planning_loop", "I think we should redo the PRD", result)
    assert "planning_loop" in result.risk_flags
    assert result.recommended_mode == "CHALLENGE"


def test_check_keyword_rules_ui_avoidance():
    result = RuleResult()
    _check_keyword_rules("ui_avoidance", "Let's add a React dashboard", result)
    assert "ui_avoidance" in result.risk_flags
    assert result.recommended_mode == "REQUIRE_OVERRIDE"


def test_check_keyword_rules_overbuild_risk():
    result = RuleResult()
    _check_keyword_rules("overbuild_risk", "Should we add analytics?", result)
    assert "overbuild_risk" in result.risk_flags


def test_check_keyword_rules_no_match():
    result = RuleResult()
    _check_keyword_rules("planning_loop", "Let's ship this today", result)
    assert result.risk_flags == []


def test_check_keyword_rules_integration_avoidance():
    result = RuleResult()
    _check_keyword_rules("integration_avoidance", "Let's add a Slack integration", result)
    assert "integration_avoidance" in result.risk_flags


def test_check_keyword_rules_project_switching():
    result = RuleResult()
    _check_keyword_rules("project_switching", "Let's switch to project B", result)
    assert "project_switching" in result.risk_flags


# ---------------------------------------------------------------------------
# _check_contract_conflict
# ---------------------------------------------------------------------------

def test_contract_conflict_no_contract():
    result = RuleResult()
    _check_contract_conflict("test message", {}, result)
    assert result.risk_flags == []


def test_contract_conflict_match():
    contract = {
        "constraints": {
            "dashboard-ban": {
                "description": "No dashboards",
                "conflict_patterns": [r"\bdashboard\b", r"\bReact\b"],
            }
        }
    }
    result = RuleResult()
    _check_contract_conflict("Let's build a dashboard", {"operating_contract": contract}, result)
    assert "contract_conflict" in result.risk_flags
    assert result.recommended_mode == "REQUIRE_OVERRIDE"


def test_contract_conflict_invalid_regex_skipped():
    contract = {
        "constraints": {
            "bad-pattern": {
                "description": "Bad",
                "conflict_patterns": [r"[invalid"],
            }
        }
    }
    result = RuleResult()
    _check_contract_conflict("anything", contract, result)
    assert result.risk_flags == []


# ---------------------------------------------------------------------------
# _check_experiment_conflict
# ---------------------------------------------------------------------------

def test_experiment_conflict_mentions_stopping():
    result = RuleResult()
    _check_experiment_conflict(
        "Should we stop the auth-experiment?",
        {"active_experiments": ["auth-experiment"]},
        result,
    )
    assert "experiment_conflict" in result.risk_flags


def test_experiment_conflict_no_experiments():
    result = RuleResult()
    _check_experiment_conflict("Should we stop it?", {}, result)
    assert result.risk_flags == []


# ---------------------------------------------------------------------------
# evaluate_rules — integration tests
# ---------------------------------------------------------------------------

def test_evaluate_rules_empty_message():
    result = evaluate_rules("")
    assert result.risk_flags == []
    assert result.recommended_mode == "ALLOW"
    assert result.confidence == 0.0


def test_evaluate_rules_catches_ui_avoidance():
    result = evaluate_rules("Let's add a React frontend")
    assert "ui_avoidance" in result.risk_flags
    assert result.recommended_mode == "REQUIRE_OVERRIDE"
    assert result.confidence > 0.6


def test_evaluate_rules_catches_planning_loop():
    result = evaluate_rules("I think we should rethink the roadmap")
    assert "planning_loop" in result.risk_flags
    assert result.recommended_mode == "CHALLENGE"


def test_evaluate_rules_catches_overbuild():
    result = evaluate_rules("Maybe we should add multi-user auth and analytics")
    assert "overbuild_risk" in result.risk_flags


def test_evaluate_rules_catches_multiple_risks():
    result = evaluate_rules(
        "Let's scrap the React dashboard and add multi-user auth"
    )
    assert "ui_avoidance" in result.risk_flags
    assert "overbuild_risk" in result.risk_flags


def test_evaluate_rules_contract_context():
    contract = {
        "constraints": {
            "no-frontend": {
                "description": "No frontend",
                "conflict_patterns": [r"\bfrontend\b"],
            }
        }
    }
    result = evaluate_rules("Let's add a frontend", context={"operating_contract": contract})
    assert "contract_conflict" in result.risk_flags


def test_evaluate_rules_experiment_context():
    result = evaluate_rules(
        "Should we cancel the click-tracking experiment?",
        context={"active_experiments": ["click-tracking"]},
    )
    assert "experiment_conflict" in result.risk_flags


def test_evaluate_rules_enabled_risks_subset():
    """Only enabled risk types are checked."""
    result = evaluate_rules(
        "Let's add a React dashboard",
        context={"enabled_risks": ["planning_loop"]},
    )
    assert "planning_loop" not in result.risk_flags
    assert "ui_avoidance" not in result.risk_flags


def test_evaluate_rules_clean_message():
    result = evaluate_rules(
        "Can you help me debug this Python script?"
    )
    assert result.risk_flags == []
    assert result.recommended_mode == "ALLOW"
    assert result.confidence == 0.0


def test_evaluate_rules_to_dict():
    result = evaluate_rules("Add a dashboard")
    d = result.to_dict()
    assert "risk_flags" in d
    assert "confidence" in d
    assert "recommended_mode" in d
    assert "matched_terms" in d
    assert isinstance(d["confidence"], float)


def test_rule_result_to_dict_empty():
    result = RuleResult()
    d = result.to_dict()
    assert d["risk_flags"] == []
    assert d["confidence"] == 0.0
    assert d["recommended_mode"] == "ALLOW"
    assert d["matched_terms"] == []
