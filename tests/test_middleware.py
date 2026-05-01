"""Tests for src/core/middleware.py — process_reflex() and helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.core.middleware import (
    _is_reflex_command,
    _build_allow_result,
    process_reflex,
)
from src.core.schemas import ReflexResult
from src.core.response_modes import get_hermes_instruction, MODE_INSTRUCTIONS


def _mock_to_dict(data: dict) -> MagicMock:
    obj = MagicMock()
    obj.to_dict.return_value = data
    return obj


# ---------------------------------------------------------------------------
# _is_reflex_command
# ---------------------------------------------------------------------------

def test_is_reflex_command_checkin():
    assert _is_reflex_command("/checkin") is True
    assert _is_reflex_command("/checkin energy 7") is True


def test_is_reflex_command_experiment():
    assert _is_reflex_command("/experiment create no-dashboard") is True


def test_is_reflex_command_patterns():
    assert _is_reflex_command("/patterns") is True


def test_is_reflex_command_reflex():
    assert _is_reflex_command("/reflex Should I build a dashboard?") is True


def test_is_reflex_command_review():
    assert _is_reflex_command("/review") is True


def test_is_reflex_command_override():
    assert _is_reflex_command("/override") is True


def test_is_reflex_command_regular_message():
    assert _is_reflex_command("Build me a dashboard") is False


def test_is_reflex_command_case_insensitive():
    assert _is_reflex_command("/CHECKIN") is True
    assert _is_reflex_command("/Reflex hello") is True


# ---------------------------------------------------------------------------
# _build_allow_result
# ---------------------------------------------------------------------------

def test_build_allow_result_returns_reflex_result():
    result = _build_allow_result("Reflex command bypass")
    assert isinstance(result, ReflexResult)
    assert result.mode == "ALLOW"
    assert result.risk_type == "none"
    assert result.confidence == 0.0


def test_build_allow_result_includes_instruction():
    result = _build_allow_result("paused", include_reflex_instructions=True)
    assert "Respond normally" in result.hermes_instruction


def test_build_allow_result_omits_instruction_when_flag_false():
    result = _build_allow_result("disabled", include_reflex_instructions=False)
    assert result.hermes_instruction == ""


# ---------------------------------------------------------------------------
# process_reflex — bypass cases
# ---------------------------------------------------------------------------

def test_process_reflex_bypasses_checkin_command():
    """Reflex commands should always return ALLOW without calling the critic."""
    with patch("src.core.pause.is_paused") as mock_paused:
        mock_paused.return_value = False
        result = process_reflex("/checkin energy 8 available 2h")

    assert result.mode == "ALLOW"
    assert result.risk_type == "none"


def test_process_reflex_bypasses_experiment_command():
    with patch("src.core.pause.is_paused") as mock_paused:
        mock_paused.return_value = False
        result = process_reflex("/experiment create no-ui")

    assert result.mode == "ALLOW"


def test_process_reflex_returns_allow_when_disabled():
    with patch("src.core.pause.is_paused") as mock_paused:
        mock_paused.return_value = False
        result = process_reflex("Should I build a dashboard?", enabled=False)

    assert result.mode == "ALLOW"


def test_process_reflex_returns_allow_when_paused():
    with patch("src.core.pause.is_paused") as mock_paused:
        mock_paused.return_value = True
        result = process_reflex("Should I build a dashboard?")

    assert result.mode == "ALLOW"


# ---------------------------------------------------------------------------
# process_reflex — full pipeline with mocked dependencies
# ---------------------------------------------------------------------------

def test_process_reflex_runs_full_pipeline_with_mocks():
    """Happy-path test: rules fire, retrieval works, critic returns CHALLENGE."""
    with patch("src.core.pause.is_paused") as mock_paused, \
         patch("src.core.rule_engine.evaluate_rules") as mock_rules, \
         patch("src.core.operating_contract.load_contract") as mock_contract, \
         patch("src.embeddings.search.search_reflex_memory") as mock_search, \
         patch("src.gbrain.storage.read_active_patterns") as mock_patterns, \
         patch("src.gbrain.storage.read_active_experiments") as mock_experiments, \
         patch("src.critic.critic") as mock_critic, \
         patch("src.gbrain.storage.write_decision") as mock_write_dec, \
         patch("src.gbrain.storage.write_signal") as mock_write_sig:

        mock_paused.return_value = False

        mock_contract.return_value = _mock_to_dict({"constraints": {}})

        mock_rule_result = MagicMock()
        mock_rule_result.to_dict.return_value = {
            "risk_flags": ["ui_avoidance"],
            "confidence": 0.78,
            "recommended_mode": "CHALLENGE",
            "matched_terms": ["dashboard"],
        }
        mock_rules.return_value = mock_rule_result

        mock_search.return_value = [
            {"id": "exp_no_dashboard", "type": "experiment", "summary": "No Dashboard Build", "score": 0.92, "title": "No Dashboard Build"}
        ]
        mock_patterns.return_value = []
        mock_experiments.return_value = [{"name": "No Dashboard Build"}]

        mock_decision = MagicMock()
        mock_decision.mode = "CHALLENGE"
        mock_decision.risk_type = "ui_avoidance"
        mock_decision.confidence = 0.86
        mock_decision.severity = "medium"
        mock_decision.reason = "Conflicts with no-dashboard experiment."
        mock_decision.recommended_action = "Ship /patterns first."
        mock_decision.allow_override = True
        mock_decision.to_dict.return_value = {
            "mode": "CHALLENGE",
            "risk_type": "ui_avoidance",
            "confidence": 0.86,
            "severity": "medium",
            "allow_override": True,
        }
        mock_critic.return_value = mock_decision

        result = process_reflex("Should I add a dashboard?")

    assert result.mode == "CHALLENGE"
    assert result.risk_type == "ui_avoidance"
    assert result.confidence == 0.86
    assert result.severity == "medium"
    assert result.decision_id is not None
    assert "Respond normally" not in result.hermes_instruction  # Should have CHALLENGE instruction
    assert "patterns" in result.hermes_instruction.lower()


def test_process_reflex_contract_conflict_overrides_critic():
    """When contract says REQUIRE_OVERRIDE, that takes precedence over critic."""
    with patch("src.core.pause.is_paused") as mock_paused, \
         patch("src.core.rule_engine.evaluate_rules") as mock_rules, \
         patch("src.core.operating_contract.load_contract") as mock_contract, \
         patch("src.embeddings.search.search_reflex_memory") as mock_search, \
         patch("src.gbrain.storage.read_active_patterns") as mock_patterns, \
         patch("src.gbrain.storage.read_active_experiments") as mock_experiments, \
         patch("src.critic.critic") as mock_critic, \
         patch("src.gbrain.storage.write_decision") as mock_dec, \
         patch("src.gbrain.storage.write_signal") as mock_sig:

        mock_paused.return_value = False
        mock_rules.return_value = _mock_to_dict({"risk_flags": [], "confidence": 0.0, "recommended_mode": "ALLOW", "matched_terms": []})
        mock_contract.return_value = _mock_to_dict({"constraints": {}})
        mock_search.return_value = []
        mock_patterns.return_value = []
        mock_experiments.return_value = []

        # Critic says ALLOW
        mock_decision = MagicMock()
        mock_decision.mode = "ALLOW"
        mock_decision.risk_type = "none"
        mock_decision.confidence = 0.0
        mock_decision.severity = "low"
        mock_decision.reason = ""
        mock_decision.recommended_action = ""
        mock_decision.allow_override = True
        mock_decision.to_dict.return_value = {"mode": "ALLOW", "risk_type": "none", "confidence": 0.0, "severity": "low"}
        mock_critic.return_value = mock_decision

        # But contract says REQUIRE_OVERRIDE for dashboard
        with patch("src.core.operating_contract.check_contract_conflict") as mock_check:
            from src.core.operating_contract import ContractConflict
            mock_check.return_value = ContractConflict(
                conflict=True,
                constraint="No dashboard",
                confidence=0.9,
                recommended_mode="REQUIRE_OVERRIDE",
            )

            result = process_reflex("Let's add a dashboard")

    assert result.mode == "REQUIRE_OVERRIDE"
    assert result.risk_type == "contract_conflict"


def test_process_reflex_graceful_degradation_on_rule_failure():
    """If rule engine raises, process_reflex still returns ALLOW (no crash)."""
    with patch("src.core.pause.is_paused") as mock_paused, \
         patch("src.core.rule_engine.evaluate_rules") as mock_rules, \
         patch("src.core.operating_contract.load_contract") as mock_contract:

        mock_paused.return_value = False
        mock_rules.side_effect = RuntimeError("database error")
        mock_contract.side_effect = RuntimeError("file not found")

        # Should not raise — degrades to ALLOW
        result = process_reflex("Should I build a dashboard?")

    assert result.mode == "ALLOW"


def test_process_reflex_graceful_degradation_on_critic_failure():
    """If critic raises, process_reflex still returns ALLOW (no crash)."""
    with patch("src.core.pause.is_paused") as mock_paused, \
         patch("src.core.rule_engine.evaluate_rules") as mock_rules, \
         patch("src.core.operating_contract.load_contract") as mock_contract, \
         patch("src.embeddings.search.search_reflex_memory") as mock_search, \
         patch("src.gbrain.storage.read_active_patterns") as mock_patterns, \
         patch("src.gbrain.storage.read_active_experiments") as mock_exps, \
         patch("src.critic.critic") as mock_critic:

        mock_paused.return_value = False
        mock_rules.return_value = _mock_to_dict({"risk_flags": [], "confidence": 0.0, "recommended_mode": "ALLOW", "matched_terms": []})
        mock_contract.return_value = _mock_to_dict({"constraints": {}})
        mock_search.return_value = []
        mock_patterns.return_value = []
        mock_exps.return_value = []
        mock_critic.side_effect = RuntimeError("API unavailable")

        result = process_reflex("Should I add a React frontend?")

    assert result.mode == "ALLOW"


def test_process_reflex_skip_retrieval_flag():
    """skip_retrieval=True bypasses the embedding search step."""
    with patch("src.core.pause.is_paused") as mock_paused, \
         patch("src.core.rule_engine.evaluate_rules") as mock_rules, \
         patch("src.core.operating_contract.load_contract") as mock_contract, \
         patch("src.embeddings.search.search_reflex_memory") as mock_search, \
         patch("src.critic.critic") as mock_critic, \
         patch("src.gbrain.storage.write_decision") as mock_dec:

        mock_paused.return_value = False
        mock_rules.return_value = _mock_to_dict({"risk_flags": [], "confidence": 0.0, "recommended_mode": "ALLOW", "matched_terms": []})
        mock_contract.return_value = _mock_to_dict({"constraints": {}})

        mock_decision = MagicMock()
        mock_decision.mode = "ALLOW"
        mock_decision.risk_type = "none"
        mock_decision.confidence = 0.0
        mock_decision.severity = "low"
        mock_decision.reason = ""
        mock_decision.recommended_action = ""
        mock_decision.allow_override = True
        mock_decision.to_dict.return_value = {"mode": "ALLOW", "risk_type": "none", "confidence": 0.0, "severity": "low"}
        mock_critic.return_value = mock_decision

        result = process_reflex("Build me a dashboard", skip_retrieval=True)

    mock_search.assert_not_called()
    assert result.mode == "ALLOW"


def test_process_reflex_skip_critic_flag():
    """skip_critic=True bypasses the LLM call."""
    with patch("src.core.pause.is_paused") as mock_paused, \
         patch("src.core.rule_engine.evaluate_rules") as mock_rules, \
         patch("src.core.operating_contract.load_contract") as mock_contract, \
         patch("src.critic.critic") as mock_critic:

        mock_paused.return_value = False
        mock_rule_result = MagicMock()
        mock_rule_result.to_dict.return_value = {"risk_flags": ["ui_avoidance"], "confidence": 0.78, "recommended_mode": "CHALLENGE", "matched_terms": ["dashboard"]}
        mock_rules.return_value = mock_rule_result
        mock_contract.return_value = _mock_to_dict({"constraints": {}})

        result = process_reflex("Let's add a dashboard", skip_critic=True)

    mock_critic.assert_not_called()
    # skip_critic bypasses the LLM, but local rules still enforce so Reflex does not fail open.
    assert result.mode == "CHALLENGE"
    assert result.risk_type == "ui_avoidance"


def test_process_reflex_logs_decision_on_challenge():
    """When mode is CHALLENGE, both decision and signal are logged to GBrain."""
    with patch("src.core.pause.is_paused") as mock_paused, \
         patch("src.core.rule_engine.evaluate_rules") as mock_rules, \
         patch("src.core.operating_contract.load_contract") as mock_contract, \
         patch("src.embeddings.search.search_reflex_memory") as mock_search, \
         patch("src.gbrain.storage.read_active_patterns") as mock_patterns, \
         patch("src.gbrain.storage.read_active_experiments") as mock_exps, \
         patch("src.critic.critic") as mock_critic, \
         patch("src.gbrain.storage.write_decision") as mock_write_dec, \
         patch("src.gbrain.storage.write_signal") as mock_write_sig:

        mock_paused.return_value = False
        mock_rule_result = MagicMock()
        mock_rule_result.to_dict.return_value = {"risk_flags": ["ui_avoidance"], "confidence": 0.78, "recommended_mode": "CHALLENGE", "matched_terms": ["dashboard"]}
        mock_rules.return_value = mock_rule_result
        mock_contract.return_value = _mock_to_dict({"constraints": {}})
        mock_search.return_value = []
        mock_patterns.return_value = []
        mock_exps.return_value = []

        mock_decision = MagicMock()
        mock_decision.mode = "CHALLENGE"
        mock_decision.risk_type = "ui_avoidance"
        mock_decision.confidence = 0.86
        mock_decision.severity = "medium"
        mock_decision.reason = "Dashboard conflicts with constraints."
        mock_decision.recommended_action = "Finish /patterns first."
        mock_decision.allow_override = True
        mock_decision.to_dict.return_value = {"mode": "CHALLENGE", "risk_type": "ui_avoidance", "confidence": 0.86, "severity": "medium"}
        mock_critic.return_value = mock_decision

        result = process_reflex("Let's add a dashboard")

    assert result.mode == "CHALLENGE"
    mock_write_dec.assert_called_once()
    mock_write_sig.assert_called_once()


def test_process_reflex_no_signal_on_allow():
    """When mode is ALLOW, no signal file is written (only decision)."""
    with patch("src.core.pause.is_paused") as mock_paused, \
         patch("src.core.rule_engine.evaluate_rules") as mock_rules, \
         patch("src.core.operating_contract.load_contract") as mock_contract, \
         patch("src.embeddings.search.search_reflex_memory") as mock_search, \
         patch("src.gbrain.storage.read_active_patterns") as mock_patterns, \
         patch("src.gbrain.storage.read_active_experiments") as mock_exps, \
         patch("src.critic.critic") as mock_critic, \
         patch("src.gbrain.storage.write_decision") as mock_write_dec, \
         patch("src.gbrain.storage.write_signal") as mock_write_sig:

        mock_paused.return_value = False
        mock_rules.return_value = _mock_to_dict({"risk_flags": [], "confidence": 0.0, "recommended_mode": "ALLOW", "matched_terms": []})
        mock_contract.return_value = _mock_to_dict({"constraints": {}})
        mock_search.return_value = []
        mock_patterns.return_value = []
        mock_exps.return_value = []

        mock_decision = MagicMock()
        mock_decision.mode = "ALLOW"
        mock_decision.risk_type = "none"
        mock_decision.confidence = 0.0
        mock_decision.severity = "low"
        mock_decision.reason = ""
        mock_decision.recommended_action = ""
        mock_decision.allow_override = True
        mock_decision.to_dict.return_value = {"mode": "ALLOW", "risk_type": "none", "confidence": 0.0, "severity": "low"}
        mock_critic.return_value = mock_decision

        result = process_reflex("Help me debug this script")

    assert result.mode == "ALLOW"
    mock_write_dec.assert_called_once()
    mock_write_sig.assert_not_called()


def test_process_reflex_local_rules_enforce_when_critic_allows():
    """If the LLM critic fails open/permits a rule hit, local rules still challenge."""
    with patch("src.core.pause.is_paused") as mock_paused, \
         patch("src.core.rule_engine.evaluate_rules") as mock_rules, \
         patch("src.core.operating_contract.load_contract") as mock_contract, \
         patch("src.core.operating_contract.check_contract_conflict") as mock_conflict, \
         patch("src.embeddings.search.search_reflex_memory") as mock_search, \
         patch("src.gbrain.storage.read_active_patterns") as mock_patterns, \
         patch("src.gbrain.storage.read_active_experiments") as mock_exps, \
         patch("src.critic.critic") as mock_critic:

        mock_paused.return_value = False
        mock_rule_result = MagicMock()
        mock_rule_result.to_dict.return_value = {
            "risk_flags": ["ui_avoidance"],
            "confidence": 0.78,
            "recommended_mode": "CHALLENGE",
            "matched_terms": ["dashboard"],
        }
        mock_rules.return_value = mock_rule_result
        mock_contract.return_value = _mock_to_dict({"constraints": {}})
        mock_conflict.return_value = MagicMock(to_dict=lambda: {"conflict": False})
        mock_search.return_value = []
        mock_patterns.return_value = []
        mock_exps.return_value = []

        mock_decision = MagicMock()
        mock_decision.mode = "ALLOW"
        mock_decision.risk_type = "none"
        mock_decision.confidence = 0.0
        mock_decision.severity = "low"
        mock_decision.reason = "Critic unavailable — defaulting to ALLOW."
        mock_decision.recommended_action = ""
        mock_decision.allow_override = True
        mock_decision.to_dict.return_value = {"mode": "ALLOW", "risk_type": "none"}
        mock_critic.return_value = mock_decision

        result = process_reflex("Should I build a dashboard?")

    assert result.mode == "CHALLENGE"
    assert result.risk_type == "ui_avoidance"
    assert result.confidence == 0.78


# ---------------------------------------------------------------------------
# ReflexResult dataclass
# ---------------------------------------------------------------------------

def test_reflex_result_is_challenge_flag():
    from src.core.schemas import ReflexResult

    for mode in ("CHALLENGE", "REQUIRE_OVERRIDE", "NOTE", "CLARIFY"):
        r = ReflexResult(
            mode=mode, risk_type="ui_avoidance", confidence=0.8,
            severity="medium", hermes_instruction="test", evidence=[],
        )
        assert r._is_challenge is True, f"{mode} should be is_challenge=True"

    for mode in ("ALLOW", "SILENT_LOG"):
        r = ReflexResult(
            mode=mode, risk_type="none", confidence=0.0,
            severity="low", hermes_instruction="", evidence=[],
        )
        assert r._is_challenge is False, f"{mode} should be is_challenge=False"


def test_reflex_result_to_dict():
    from src.core.schemas import ReflexResult

    r = ReflexResult(
        mode="CHALLENGE",
        risk_type="ui_avoidance",
        confidence=0.86,
        severity="medium",
        hermes_instruction="Challenge this.",
        evidence=[{"id": "exp_1", "type": "experiment"}],
        decision_id="decision_20260501_001",
    )
    d = r.to_dict()
    assert d["mode"] == "CHALLENGE"
    assert d["is_challenge"] is True
    assert d["evidence"][0]["id"] == "exp_1"


# ---------------------------------------------------------------------------
# Response modes
# ---------------------------------------------------------------------------

def test_all_modes_have_instructions():
    from src.core.response_modes import MODE_INSTRUCTIONS
    expected = {"ALLOW", "NOTE", "CHALLENGE", "CLARIFY", "REQUIRE_OVERRIDE", "SILENT_LOG"}
    assert set(MODE_INSTRUCTIONS.keys()) == expected


def test_get_hermes_instruction_allow():
    inst = get_hermes_instruction("ALLOW")
    assert "Respond normally" in inst


def test_get_hermes_instruction_challenge():
    inst = get_hermes_instruction("CHALLENGE")
    assert "challenge" in inst.lower() or "push back" in inst.lower()


def test_get_hermes_instruction_require_override():
    inst = get_hermes_instruction("REQUIRE_OVERRIDE")
    assert "override" in inst.lower()


def test_get_hermes_instruction_unknown_returns_empty():
    assert get_hermes_instruction("BANANA_MODE") == ""
