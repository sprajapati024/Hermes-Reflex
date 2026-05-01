"""Tests for src/core/router.py — route_message()."""

from __future__ import annotations

import pytest

from src.core.router import route_message


# ---------------------------------------------------------------------------
# SAFE path — no risk signals
# ---------------------------------------------------------------------------

def test_route_safe_when_no_rules_or_contract():
    result = route_message("What should I eat for lunch?", context={
        "rule_result": {"risk_flags": [], "recommended_mode": "ALLOW", "matched_terms": []},
        "contract_conflict": {"conflict": False},
    })
    assert result["route"] == "SAFE"
    assert result["requires_retrieval"] is False
    assert result["requires_critic"] is False
    assert result["recommended_mode"] == "ALLOW"


def test_route_safe_with_empty_context():
    result = route_message("How does this work?")
    assert result["route"] == "SAFE"
    assert result["requires_retrieval"] is False


def test_route_safe_with_none_context():
    result = route_message("Help me debug this script", context=None)
    assert result["route"] == "SAFE"


# ---------------------------------------------------------------------------
# RISKY path — rule match
# ---------------------------------------------------------------------------

def test_route_risky_on_rule_match():
    result = route_message("Let's add a dashboard", context={
        "rule_result": {
            "risk_flags": ["ui_avoidance"],
            "recommended_mode": "REQUIRE_OVERRIDE",
            "matched_terms": ["dashboard"],
        },
        "contract_conflict": {"conflict": False},
    })
    assert result["route"] == "RISKY"
    assert result["requires_retrieval"] is True
    assert result["requires_critic"] is True
    assert result["recommended_mode"] == "REQUIRE_OVERRIDE"
    assert "ui_avoidance" in result["reason"]


def test_route_risky_includes_matched_terms():
    result = route_message("Add a React frontend", context={
        "rule_result": {
            "risk_flags": ["ui_avoidance"],
            "recommended_mode": "REQUIRE_OVERRIDE",
            "matched_terms": ["React", "frontend"],
        },
        "contract_conflict": {"conflict": False},
    })
    assert result["route"] == "RISKY"
    assert "React" in result["matched_terms"] or "frontend" in result["matched_terms"]


def test_route_risky_on_multiple_rule_flags():
    result = route_message("Build a SaaS dashboard", context={
        "rule_result": {
            "risk_flags": ["ui_avoidance", "overbuild_risk"],
            "recommended_mode": "REQUIRE_OVERRIDE",
            "matched_terms": ["dashboard", "SaaS"],
        },
        "contract_conflict": {"conflict": False},
    })
    assert result["route"] == "RISKY"


# ---------------------------------------------------------------------------
# RISKY path — contract conflict
# ---------------------------------------------------------------------------

def test_route_risky_on_contract_conflict():
    result = route_message("Let's build a dashboard", context={
        "rule_result": {"risk_flags": [], "recommended_mode": "ALLOW", "matched_terms": []},
        "contract_conflict": {
            "conflict": True,
            "recommended_mode": "REQUIRE_OVERRIDE",
            "matched_term": "dashboard",
        },
    })
    assert result["route"] == "RISKY"
    assert result["requires_retrieval"] is True
    assert result["requires_critic"] is True
    assert result["recommended_mode"] == "REQUIRE_OVERRIDE"
    assert "Contract conflict" in result["reason"]


def test_route_risky_contract_includes_matched_term():
    result = route_message("Add a frontend", context={
        "rule_result": {"risk_flags": [], "recommended_mode": "ALLOW", "matched_terms": []},
        "contract_conflict": {
            "conflict": True,
            "recommended_mode": "REQUIRE_OVERRIDE",
            "matched_term": "frontend",
        },
    })
    assert result["route"] == "RISKY"
    assert "frontend" in result["matched_terms"]


def test_route_risky_contract_missing_matched_term():
    """matched_term may be absent — should not error."""
    result = route_message("Do something risky", context={
        "rule_result": {"risk_flags": [], "recommended_mode": "ALLOW", "matched_terms": []},
        "contract_conflict": {
            "conflict": True,
            "recommended_mode": "REQUIRE_OVERRIDE",
        },
    })
    assert result["route"] == "RISKY"


# ---------------------------------------------------------------------------
# Rule overrides contract check ordering
# ---------------------------------------------------------------------------

def test_rule_match_takes_precedence_over_safe_contract():
    """Rule flag → RISKY even if contract says no conflict."""
    result = route_message("Redo the PRD", context={
        "rule_result": {
            "risk_flags": ["planning_loop"],
            "recommended_mode": "CHALLENGE",
            "matched_terms": ["Redo the PRD"],
        },
        "contract_conflict": {"conflict": False},
    })
    assert result["route"] == "RISKY"
    assert result["recommended_mode"] == "CHALLENGE"


# ---------------------------------------------------------------------------
# Return shape
# ---------------------------------------------------------------------------

def test_route_result_has_all_required_keys():
    result = route_message("Hello world")
    required = {"route", "reason", "matched_terms", "requires_retrieval", "requires_critic", "recommended_mode"}
    assert required.issubset(result.keys())
