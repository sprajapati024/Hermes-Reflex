"""Tests for src/core/operating_contract.py."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from src.core.operating_contract import (
    DEFAULT_CONSTRAINTS,
    CONFLICT_TERMS,
    CONSTRAINT_SEVERITY,
    ContractConflict,
    OperatingContract,
    check_contract_conflict,
    ensure_default_contract,
)

# ---------------------------------------------------------------------------
# Test-level isolation: each test gets its own GBrain root via env var.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_gbrain_root(tmp_path):
    """Set HERMES_REFLEX_GBRAIN_ROOT for every test to an isolated temp dir."""
    gbrain_root = tmp_path / "gbrain"
    gbrain_root.mkdir(parents=True)
    os.environ["HERMES_REFLEX_GBRAIN_ROOT"] = str(gbrain_root)
    yield gbrain_root


@pytest.fixture
def contract_with_constraints():
    """A contract with known constraints for conflict testing."""
    return OperatingContract(
        active_goal="Ship Hermes Reflex v1",
        constraints=[
            "No dashboard",
            "No frontend",
            "Telegram commands only",
            "GBrain markdown storage",
            "No new integrations before core commands work",
        ],
        reflex_authority="Hermes Reflex may challenge requests that conflict with this contract.",
        override_policy="The user can override, but overrides must be logged.",
    )


# ---------------------------------------------------------------------------
# DEFAULT_CONSTRAINTS
# ---------------------------------------------------------------------------

def test_default_constraints_defined():
    assert len(DEFAULT_CONSTRAINTS) > 0
    assert "No dashboard" in DEFAULT_CONSTRAINTS
    assert "No frontend" in DEFAULT_CONSTRAINTS


def test_default_constraints_no_duplicates():
    assert len(DEFAULT_CONSTRAINTS) == len(set(DEFAULT_CONSTRAINTS))


# ---------------------------------------------------------------------------
# CONFLICT_TERMS
# ---------------------------------------------------------------------------

def test_conflict_terms_defined():
    for constraint in DEFAULT_CONSTRAINTS:
        if constraint in CONFLICT_TERMS:
            assert len(CONFLICT_TERMS[constraint]) > 0


def test_conflict_terms_are_valid_regexes():
    for constraint, patterns in CONFLICT_TERMS.items():
        for p in patterns:
            try:
                re.compile(p)
            except re.error as e:
                pytest.fail(f"Invalid regex in {constraint!r}: {p!r} — {e}")


# ---------------------------------------------------------------------------
# ContractConflict dataclass
# ---------------------------------------------------------------------------

def test_contract_conflict_no_conflict():
    result = ContractConflict(conflict=False)
    assert result.conflict is False
    assert result.constraint is None
    assert result.recommended_mode == "ALLOW"


def test_contract_conflict_with_data():
    result = ContractConflict(
        conflict=True,
        constraint="No dashboard",
        confidence=0.9,
        recommended_mode="REQUIRE_OVERRIDE",
        matched_term=r"\bdashboard\b",
    )
    assert result.conflict is True
    assert result.constraint == "No dashboard"
    assert result.confidence == 0.9
    assert result.recommended_mode == "REQUIRE_OVERRIDE"


def test_contract_conflict_to_dict():
    result = ContractConflict(
        conflict=True,
        constraint="No frontend",
        confidence=0.85,
        recommended_mode="CHALLENGE",
        matched_term=r"React",
    )
    d = result.to_dict()
    assert d["conflict"] is True
    assert d["constraint"] == "No frontend"
    assert d["confidence"] == 0.85
    assert d["recommended_mode"] == "CHALLENGE"


# ---------------------------------------------------------------------------
# OperatingContract dataclass
# ---------------------------------------------------------------------------

def test_operating_contract_from_dict():
    data = {
        "active_goal": "Ship v1",
        "constraints": ["No dashboard"],
        "reflex_authority": "May challenge.",
        "override_policy": "Log overrides.",
    }
    c = OperatingContract.from_dict(data)
    assert c.active_goal == "Ship v1"
    assert c.constraints == ["No dashboard"]
    assert c.reflex_authority == "May challenge."
    assert c.override_policy == "Log overrides."


def test_operating_contract_to_dict_roundtrip():
    original = OperatingContract(
        active_goal="Ship Hermes Reflex v1",
        constraints=["No dashboard", "No frontend"],
        reflex_authority="Challenge conflicts.",
        override_policy="Log overrides.",
    )
    d = original.to_dict()
    rebuilt = OperatingContract.from_dict(d)
    assert rebuilt.active_goal == original.active_goal
    assert rebuilt.constraints == original.constraints
    assert rebuilt.reflex_authority == original.reflex_authority
    assert rebuilt.override_policy == original.override_policy


# ---------------------------------------------------------------------------
# ensure_default_contract
# ---------------------------------------------------------------------------

def test_ensure_default_contract_creates_file(isolated_gbrain_root):
    contract = ensure_default_contract()
    assert contract.active_goal == "Ship Hermes Reflex v1"
    assert len(contract.constraints) >= 5
    assert (isolated_gbrain_root / "reflex" / "contracts" / "current-operating-contract.md").exists()


def test_ensure_default_contract_idempotent(isolated_gbrain_root):
    c1 = ensure_default_contract()
    c2 = ensure_default_contract()
    assert c1.active_goal == c2.active_goal
    assert c1.constraints == c2.constraints


def test_ensure_default_contract_uses_gbrain_root(isolated_gbrain_root):
    ensure_default_contract()
    reflex_root = isolated_gbrain_root / "reflex"
    assert (reflex_root / "contracts" / "current-operating-contract.md").exists()


# ---------------------------------------------------------------------------
# check_contract_conflict — no conflict
# ---------------------------------------------------------------------------

def test_no_conflict_normal_message(contract_with_constraints):
    result = check_contract_conflict(
        "Let's continue with Phase 2",
        contract=contract_with_constraints,
    )
    assert result.conflict is False


def test_no_conflict_case_insensitive(contract_with_constraints):
    result = check_contract_conflict(
        "Maybe we should BUILD A DASHBOARD",
        contract=contract_with_constraints,
    )
    assert result.conflict is True
    assert result.constraint == "No dashboard"


# ---------------------------------------------------------------------------
# check_contract_conflict — dashboard
# ---------------------------------------------------------------------------

def test_conflict_dashboard_exact_phrase(contract_with_constraints):
    result = check_contract_conflict(
        "Let's add a dashboard for patterns",
        contract=contract_with_constraints,
    )
    assert result.conflict is True
    assert result.constraint == "No dashboard"
    assert result.recommended_mode == "REQUIRE_OVERRIDE"


def test_conflict_dashboard_dash_variant(contract_with_constraints):
    result = check_contract_conflict(
        "Can we try a dash board view?",
        contract=contract_with_constraints,
    )
    assert result.conflict is True
    assert result.constraint == "No dashboard"


def test_conflict_dashboard_visualization(contract_with_constraints):
    result = check_contract_conflict(
        "Maybe we should visualize patterns",
        contract=contract_with_constraints,
    )
    assert result.conflict is True
    assert result.constraint == "No dashboard"


# ---------------------------------------------------------------------------
# check_contract_conflict — frontend
# ---------------------------------------------------------------------------

def test_conflict_frontend_react(contract_with_constraints):
    result = check_contract_conflict(
        "Let's build this in React",
        contract=contract_with_constraints,
    )
    assert result.conflict is True
    assert result.constraint == "No frontend"


def test_conflict_frontend_tailwind(contract_with_constraints):
    result = check_contract_conflict(
        "Add Tailwind styling",
        contract=contract_with_constraints,
    )
    assert result.conflict is True
    assert result.constraint == "No frontend"


def test_conflict_frontend_ui_polish(contract_with_constraints):
    result = check_contract_conflict(
        "Let's do some UI polish",
        contract=contract_with_constraints,
    )
    assert result.conflict is True
    assert result.constraint == "No frontend"


# ---------------------------------------------------------------------------
# check_contract_conflict — integrations
# ---------------------------------------------------------------------------

def test_conflict_new_integration_gmail(contract_with_constraints):
    result = check_contract_conflict(
        "Can we add Gmail integration?",
        contract=contract_with_constraints,
    )
    assert result.conflict is True
    assert result.constraint == "No new integrations before core commands work"


def test_conflict_new_integration_calendar(contract_with_constraints):
    result = check_contract_conflict(
        "Add Google calendar sync",
        contract=contract_with_constraints,
    )
    assert result.conflict is True
    assert result.constraint == "No new integrations before core commands work"


def test_conflict_new_integration_slack(contract_with_constraints):
    result = check_contract_conflict(
        "Let's add a Slack bot",
        contract=contract_with_constraints,
    )
    assert result.conflict is True
    assert result.constraint == "No new integrations before core commands work"


# ---------------------------------------------------------------------------
# check_contract_conflict — telegram only
# ---------------------------------------------------------------------------

def test_conflict_telegram_only_browser_plugin(contract_with_constraints):
    result = check_contract_conflict(
        "Add a browser plugin for Reflex",
        contract=contract_with_constraints,
    )
    assert result.conflict is True
    assert result.constraint == "Telegram commands only"


def test_conflict_telegram_only_web_ui(contract_with_constraints):
    result = check_contract_conflict(
        "Can we have a web interface?",
        contract=contract_with_constraints,
    )
    assert result.conflict is True
    assert result.constraint == "Telegram commands only"


# ---------------------------------------------------------------------------
# check_contract_conflict — severity → mode mapping
# ---------------------------------------------------------------------------

def test_high_severity_requires_override():
    c = OperatingContract(
        active_goal="Ship v1",
        constraints=["No dashboard"],
        reflex_authority="Challenge.",
        override_policy="Log.",
    )
    result = check_contract_conflict("Build a dashboard", contract=c)
    assert result.conflict is True
    assert result.recommended_mode == "REQUIRE_OVERRIDE"


def test_medium_severity_challenges():
    c = OperatingContract(
        active_goal="Ship v1",
        constraints=["No new integrations before core commands work"],
        reflex_authority="Challenge.",
        override_policy="Log.",
    )
    result = check_contract_conflict("Add Gmail integration", contract=c)
    assert result.conflict is True
    assert result.recommended_mode == "CHALLENGE"


# ---------------------------------------------------------------------------
# check_contract_conflict — confidence scores
# ---------------------------------------------------------------------------

def test_exact_constraint_match_has_higher_confidence():
    c = OperatingContract(
        active_goal="Ship v1",
        constraints=["No dashboard"],
        reflex_authority="Challenge.",
        override_policy="Log.",
    )
    exact = check_contract_conflict("No dashboard is the rule", contract=c)
    regex = check_contract_conflict("Let's add a dashboard", contract=c)
    assert exact.confidence > regex.confidence
