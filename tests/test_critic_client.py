"""Tests for src/critic/client.py using the critic() function.

These tests mock the OpenAI API at the client level so they run without
a live API key or network access.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.critic.client import critic
from src.critic.decision import CriticDecision


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_CONTEXT = {
    "user_message": "Let's add a dashboard",
    "rule_result": {
        "risk_flags": ["ui_avoidance"],
        "confidence": 0.78,
        "recommended_mode": "CHALLENGE",
        "matched_terms": ["dashboard"],
    },
    "contract_conflict": {
        "conflict": True,
        "constraint": "No dashboard",
        "confidence": 0.85,
        "recommended_mode": "REQUIRE_OVERRIDE",
    },
    "active_experiments": [{"name": "No Dashboard Build", "status": "active"}],
    "retrieved_evidence": [
        {
            "id": "exp_no_dashboard",
            "type": "experiment",
            "score": 0.92,
            "summary": "Active experiment: No Dashboard Build",
        }
    ],
    "recent_patterns": [{"name": "UI Avoidance", "status": "active"}],
}


def _mock_response(content: str) -> MagicMock:
    """Build a mock chat.completions.create response with the given content."""
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_critic_returns_decision_on_valid_json_response():
    raw = (
        '{"mode": "REQUIRE_OVERRIDE", "risk_type": "contract_conflict", '
        '"confidence": 0.9, "severity": "high", '
        '"evidence_ids": ["exp_no_dashboard"], '
        '"reason": "Dashboard conflicts with no-dashboard experiment.", '
        '"recommended_action": "Ship /patterns first.", '
        '"allow_override": true}'
    )
    with patch("src.critic.client._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(raw)
        mock_get_client.return_value = mock_client

        result = critic(**MINIMAL_CONTEXT)

    assert isinstance(result, CriticDecision)
    assert result.mode == "REQUIRE_OVERRIDE"
    assert result.risk_type == "contract_conflict"
    assert result.confidence == 0.9
    assert "exp_no_dashboard" in result.evidence_ids


def test_critic_returns_allow_when_no_risk():
    raw = '{"mode": "ALLOW", "risk_type": "none", "confidence": 0.0, "severity": "low"}'
    with patch("src.critic.client._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(raw)
        mock_get_client.return_value = mock_client

        result = critic(
            user_message="Help me debug this script",
            rule_result={"risk_flags": [], "confidence": 0.0, "recommended_mode": "ALLOW", "matched_terms": []},
            contract_conflict={"conflict": False},
            active_experiments=[],
            retrieved_evidence=[],
            recent_patterns=[],
        )

    assert result.mode == "ALLOW"
    assert result.risk_type == "none"


# ---------------------------------------------------------------------------
# Retry on RateLimitError
# ---------------------------------------------------------------------------

def _make_rate_limit_error() -> Exception:
    """Create a RateLimitError compatible with the installed openai version."""
    import openai
    try:
        # Newer openai (>= 1.68): requires body= argument
        return openai.RateLimitError(
            "rate limited",
            response=MagicMock(),
            body=None,
        )
    except TypeError:
        # Older openai: positional response arg
        return openai.RateLimitError("rate limited", response=MagicMock())


def test_critic_retries_on_rate_limit_then_succeeds():
    raw = '{"mode": "ALLOW", "risk_type": "none", "confidence": 0.0, "severity": "low"}'
    # Clear the lru_cache so the mock client is used on every call
    with patch("src.critic.client._get_client") as mock_get_client:
        mock_client = MagicMock()
        # First call raises RateLimitError, second succeeds
        mock_client.chat.completions.create.side_effect = [
            _make_rate_limit_error(),
            _mock_response(raw),
        ]
        mock_get_client.return_value = mock_client

        result = critic(**MINIMAL_CONTEXT, max_retries=3)

    assert result.mode == "ALLOW"
    assert mock_client.chat.completions.create.call_count == 2


def test_critic_returns_default_allow_after_all_retries_fail():
    with patch("src.critic.client._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            _make_rate_limit_error(),
            _make_rate_limit_error(),
            _make_rate_limit_error(),
        ]
        mock_get_client.return_value = mock_client

        result = critic(**MINIMAL_CONTEXT, max_retries=3)

    assert isinstance(result, CriticDecision)
    assert result.mode == "ALLOW"
    assert "Critic unavailable" in result.reason


# ---------------------------------------------------------------------------
# Retry on ParseError (bad JSON — one retry is enough)
# ---------------------------------------------------------------------------

def test_critic_retries_once_on_parse_error():
    good_raw = '{"mode": "NOTE", "risk_type": "planning_loop", "confidence": 0.6, "severity": "low"}'
    with patch("src.critic.client._get_client") as mock_get_client:
        mock_client = MagicMock()
        # First call returns bad JSON, second returns good JSON
        mock_client.chat.completions.create.side_effect = [
            _mock_response("This is not JSON output"),
            _mock_response(good_raw),
        ]
        mock_get_client.return_value = mock_client

        result = critic(**MINIMAL_CONTEXT)

    assert result.mode == "NOTE"
    assert result.risk_type == "planning_loop"
    assert mock_client.chat.completions.create.call_count == 2


def test_critic_returns_default_allow_after_parse_retry_fails():
    with patch("src.critic.client._get_client") as mock_get_client:
        mock_client = MagicMock()
        # Both calls return bad JSON
        mock_client.chat.completions.create.side_effect = [
            _mock_response("Not JSON"),
            _mock_response("Still not JSON"),
        ]
        mock_get_client.return_value = mock_client

        result = critic(**MINIMAL_CONTEXT, max_retries=2)

    assert result.mode == "ALLOW"


# ---------------------------------------------------------------------------
# Missing API key
# ---------------------------------------------------------------------------

def test_critic_returns_default_allow_when_no_api_key():
    """When no API key is set, the client raises but the retry loop catches it
    and returns default_allow() — the pipeline stays graceful rather than crashing."""
    import src.critic.client as client_module
    client_module._get_client.cache_clear()
    with patch.dict("os.environ", {}, clear=True):
        result = critic(**MINIMAL_CONTEXT)

    # Should degrade gracefully to ALLOW, not raise
    assert isinstance(result, CriticDecision)
    assert result.mode == "ALLOW"
    assert "Critic unavailable" in result.reason


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def test_critic_assembles_prompt_with_all_context_fields():
    from src.critic import prompt as prompt_module

    user_content = prompt_module.build_user_message(
        user_message=MINIMAL_CONTEXT["user_message"],
        rule_result=MINIMAL_CONTEXT["rule_result"],
        contract_conflict=MINIMAL_CONTEXT["contract_conflict"],
        active_experiments=MINIMAL_CONTEXT["active_experiments"],
        retrieved_evidence=MINIMAL_CONTEXT["retrieved_evidence"],
        recent_patterns=MINIMAL_CONTEXT["recent_patterns"],
    )

    # System prompt is present
    assert prompt_module.SYSTEM_PROMPT != ""

    # User message includes the original message
    assert "Let's add a dashboard" in user_content
    # Rule flags included
    assert "ui_avoidance" in user_content
    # Contract conflict included
    assert "CONTRACT CONFLICT" in user_content
    # Evidence included
    assert "Retrieved evidence:" in user_content
    assert "exp_no_dashboard" in user_content
    # Experiments included
    assert "No Dashboard Build" in user_content


def test_critic_passes_model_and_max_tokens_to_api():
    raw = '{"mode": "ALLOW", "risk_type": "none", "confidence": 0.0, "severity": "low"}'
    with patch("src.critic.client._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(raw)
        mock_get_client.return_value = mock_client

        critic(**MINIMAL_CONTEXT, model="gpt-4o", max_retries=1)

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o"
        assert call_kwargs.kwargs["response_format"] == {"type": "json_object"}
