"""Tests for the Reflex v2 adaptive pipeline in src/core/middleware.py.

Covers:
  - Safe messages skip retrieval and critic
  - Risky messages still trigger contract/rule enforcement
  - Critic timeout falls back to deterministic rules without blocking
  - Decision cache returns cached results
  - Deferred logging is called for non-safe paths
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call
import time

import pytest

from src.core.middleware import process_reflex, _make_cache_key, _decision_cache, _cache_lock
from src.core.schemas import ReflexResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _allow_rule_result():
    m = MagicMock()
    m.to_dict.return_value = {
        "risk_flags": [], "confidence": 0.0,
        "recommended_mode": "ALLOW", "matched_terms": [],
    }
    return m


def _risky_rule_result(risk="ui_avoidance", mode="CHALLENGE"):
    m = MagicMock()
    m.to_dict.return_value = {
        "risk_flags": [risk], "confidence": 0.78,
        "recommended_mode": mode, "matched_terms": ["dashboard"],
    }
    return m


def _no_conflict():
    m = MagicMock()
    m.to_dict.return_value = {"conflict": False}
    return m


def _allow_critic():
    dec = MagicMock()
    dec.mode = "ALLOW"
    dec.risk_type = "none"
    dec.confidence = 0.0
    dec.severity = "low"
    dec.reason = ""
    dec.recommended_action = ""
    dec.allow_override = True
    dec.to_dict.return_value = {"mode": "ALLOW", "risk_type": "none"}
    return dec


# ---------------------------------------------------------------------------
# SAFE fast path — retrieval and critic must not be called
# ---------------------------------------------------------------------------

def test_safe_message_skips_retrieval():
    """A safe message must not call the embedding search."""
    with patch("src.core.pause.is_paused", return_value=False), \
         patch("src.core.rule_engine.evaluate_rules", return_value=_allow_rule_result()), \
         patch("src.core.operating_contract.load_contract", return_value=MagicMock(to_dict=lambda: {"constraints": {}})), \
         patch("src.core.operating_contract.check_contract_conflict", return_value=_no_conflict()), \
         patch("src.gbrain.storage.read_active_experiments", return_value=[]), \
         patch("src.embeddings.search.search_reflex_memory") as mock_search, \
         patch("src.critic.critic") as mock_critic:

        result = process_reflex("What should I eat for lunch?")

    mock_search.assert_not_called()
    assert result.mode == "ALLOW"


def test_safe_message_skips_critic():
    """A safe message must not call the LLM critic."""
    with patch("src.core.pause.is_paused", return_value=False), \
         patch("src.core.rule_engine.evaluate_rules", return_value=_allow_rule_result()), \
         patch("src.core.operating_contract.load_contract", return_value=MagicMock(to_dict=lambda: {"constraints": {}})), \
         patch("src.core.operating_contract.check_contract_conflict", return_value=_no_conflict()), \
         patch("src.gbrain.storage.read_active_experiments", return_value=[]), \
         patch("src.critic.critic") as mock_critic:

        result = process_reflex("Help me think through this problem.")

    mock_critic.assert_not_called()
    assert result.mode == "ALLOW"


def test_safe_message_returns_allow_immediately():
    """Safe messages skip GBrain logging (no write_decision call)."""
    with patch("src.core.pause.is_paused", return_value=False), \
         patch("src.core.rule_engine.evaluate_rules", return_value=_allow_rule_result()), \
         patch("src.core.operating_contract.load_contract", return_value=MagicMock(to_dict=lambda: {"constraints": {}})), \
         patch("src.core.operating_contract.check_contract_conflict", return_value=_no_conflict()), \
         patch("src.gbrain.storage.read_active_experiments", return_value=[]), \
         patch("src.gbrain.storage.write_decision") as mock_dec, \
         patch("src.gbrain.storage.write_signal") as mock_sig:

        result = process_reflex("Can you summarise this?")

    assert result.mode == "ALLOW"
    mock_dec.assert_not_called()
    mock_sig.assert_not_called()


# ---------------------------------------------------------------------------
# RISKY path — rule enforcement still fires
# ---------------------------------------------------------------------------

def test_risky_dashboard_request_blocks():
    """A dashboard request must be routed RISKY and challenged."""
    with patch("src.core.pause.is_paused", return_value=False), \
         patch("src.core.rule_engine.evaluate_rules", return_value=_risky_rule_result("ui_avoidance", "CHALLENGE")), \
         patch("src.core.operating_contract.load_contract", return_value=MagicMock(to_dict=lambda: {"constraints": {}})), \
         patch("src.core.operating_contract.check_contract_conflict", return_value=_no_conflict()), \
         patch("src.gbrain.storage.read_active_experiments", return_value=[]), \
         patch("src.embeddings.search.search_reflex_memory", return_value=[]), \
         patch("src.gbrain.storage.read_active_patterns", return_value=[]), \
         patch("src.critic.critic") as mock_critic, \
         patch("src.gbrain.storage.write_decision"), \
         patch("src.gbrain.storage.write_signal"):

        dec = MagicMock()
        dec.mode = "CHALLENGE"
        dec.risk_type = "ui_avoidance"
        dec.confidence = 0.86
        dec.severity = "medium"
        dec.reason = "Dashboard conflicts with no-ui policy."
        dec.recommended_action = "Stay on the current task."
        dec.allow_override = True
        dec.to_dict.return_value = {"mode": "CHALLENGE", "risk_type": "ui_avoidance"}
        mock_critic.return_value = dec

        result = process_reflex("Maybe we should add a dashboard for this.")

    assert result.mode == "CHALLENGE"
    assert result.risk_type == "ui_avoidance"


def test_risky_path_calls_retrieval():
    """Risky messages must trigger the embedding retrieval step."""
    with patch("src.core.pause.is_paused", return_value=False), \
         patch("src.core.rule_engine.evaluate_rules", return_value=_risky_rule_result()), \
         patch("src.core.operating_contract.load_contract", return_value=MagicMock(to_dict=lambda: {"constraints": {}})), \
         patch("src.core.operating_contract.check_contract_conflict", return_value=_no_conflict()), \
         patch("src.gbrain.storage.read_active_experiments", return_value=[]), \
         patch("src.embeddings.search.search_reflex_memory") as mock_search, \
         patch("src.gbrain.storage.read_active_patterns", return_value=[]), \
         patch("src.critic.critic", return_value=_allow_critic()), \
         patch("src.gbrain.storage.write_decision"), \
         patch("src.gbrain.storage.write_signal"):

        mock_search.return_value = []
        result = process_reflex("Let's build a dashboard.")

    mock_search.assert_called_once()


# ---------------------------------------------------------------------------
# Critic timeout — falls back to rule result, no exception raised
# ---------------------------------------------------------------------------

def test_critic_timeout_uses_rule_fallback():
    """When the critic times out, the rule result must be used and no exception raised."""
    import concurrent.futures

    with patch("src.core.pause.is_paused", return_value=False), \
         patch("src.core.rule_engine.evaluate_rules", return_value=_risky_rule_result("ui_avoidance", "CHALLENGE")), \
         patch("src.core.operating_contract.load_contract", return_value=MagicMock(to_dict=lambda: {"constraints": {}})), \
         patch("src.core.operating_contract.check_contract_conflict", return_value=_no_conflict()), \
         patch("src.gbrain.storage.read_active_experiments", return_value=[]), \
         patch("src.embeddings.search.search_reflex_memory", return_value=[]), \
         patch("src.gbrain.storage.read_active_patterns", return_value=[]), \
         patch("src.gbrain.storage.write_decision"), \
         patch("src.gbrain.storage.write_signal"), \
         patch("src.core.middleware._call_critic_timed", return_value=None) as mock_timed:

        result = process_reflex("Let's add a React frontend.", skip_retrieval=True)

    # Critic returned None (timeout simulated) — rule fallback must enforce CHALLENGE
    assert result.mode == "CHALLENGE"
    assert result.risk_type == "ui_avoidance"
    mock_timed.assert_called_once()


def test_critic_timeout_does_not_block():
    """Verify that a slow critic is cut off by the timeout, not waited on.

    Uses the shared _critic_executor directly via patching src.critic.critic
    (the function the executor submits).  The shared executor means no new
    ThreadPoolExecutor is created per call, and future.result(timeout=...) on
    the shared pool's future returns promptly on timeout.
    """
    import threading

    slow_event = threading.Event()

    def _slow_critic(**kwargs):
        slow_event.wait(timeout=10)  # blocks until we set the event

    with patch("src.core.pause.is_paused", return_value=False), \
         patch("src.core.rule_engine.evaluate_rules", return_value=_risky_rule_result()), \
         patch("src.core.operating_contract.load_contract", return_value=MagicMock(to_dict=lambda: {"constraints": {}})), \
         patch("src.core.operating_contract.check_contract_conflict", return_value=_no_conflict()), \
         patch("src.gbrain.storage.read_active_experiments", return_value=[]), \
         patch("src.embeddings.search.search_reflex_memory", return_value=[]), \
         patch("src.gbrain.storage.read_active_patterns", return_value=[]), \
         patch("src.gbrain.storage.write_decision"), \
         patch("src.gbrain.storage.write_signal"), \
         patch.dict("os.environ", {"HERMES_REFLEX_CRITIC_TIMEOUT_MS": "150"}), \
         patch("src.critic.critic", side_effect=_slow_critic):

        start = time.monotonic()
        result = process_reflex("Let's add a SaaS layer.")
        elapsed_ms = (time.monotonic() - start) * 1000

    slow_event.set()  # release the background thread

    # Should finish well within 2 s even though the critic sleeps for 10 s
    assert elapsed_ms < 2000, f"Took {elapsed_ms:.0f} ms — critic timeout not enforced"
    # Rule fallback must still enforce a non-ALLOW mode
    assert result.mode in ("CHALLENGE", "REQUIRE_OVERRIDE")


# ---------------------------------------------------------------------------
# Decision cache
# ---------------------------------------------------------------------------

def test_decision_cache_returns_cached_result():
    """Second call with the same message must hit the cache."""
    _decision_cache.clear()

    common_patches = dict(
        is_paused=False,
        evaluate_rules=_risky_rule_result(),
        load_contract=MagicMock(to_dict=lambda: {"constraints": {}}),
        check_contract_conflict=_no_conflict(),
        read_active_experiments=[],
        search_reflex_memory=[],
        read_active_patterns=[],
        write_decision=None,
        write_signal=None,
    )

    with patch("src.core.pause.is_paused", return_value=False), \
         patch("src.core.rule_engine.evaluate_rules", return_value=_risky_rule_result()), \
         patch("src.core.operating_contract.load_contract", return_value=MagicMock(to_dict=lambda: {"constraints": {}})), \
         patch("src.core.operating_contract.check_contract_conflict", return_value=_no_conflict()), \
         patch("src.gbrain.storage.read_active_experiments", return_value=[]), \
         patch("src.embeddings.search.search_reflex_memory", return_value=[]), \
         patch("src.gbrain.storage.read_active_patterns", return_value=[]), \
         patch("src.critic.critic") as mock_critic, \
         patch("src.gbrain.storage.write_decision"), \
         patch("src.gbrain.storage.write_signal"):

        dec = MagicMock()
        dec.mode = "CHALLENGE"
        dec.risk_type = "ui_avoidance"
        dec.confidence = 0.8
        dec.severity = "medium"
        dec.reason = "rule match"
        dec.recommended_action = ""
        dec.allow_override = True
        dec.to_dict.return_value = {"mode": "CHALLENGE"}
        mock_critic.return_value = dec

        result1 = process_reflex("Add a dashboard please.", skip_retrieval=True)
        result2 = process_reflex("Add a dashboard please.", skip_retrieval=True)

    # Critic should only have been called once; second call hits cache
    assert mock_critic.call_count == 1
    assert result1.mode == result2.mode

    _decision_cache.clear()


# ---------------------------------------------------------------------------
# Existing bypass / pause behaviour unchanged
# ---------------------------------------------------------------------------

def test_command_bypass_still_works():
    result = process_reflex("/checkin energy 8")
    assert result.mode == "ALLOW"


def test_disabled_still_works():
    with patch("src.core.pause.is_paused", return_value=False):
        result = process_reflex("Build a dashboard", enabled=False)
    assert result.mode == "ALLOW"


def test_paused_still_works():
    with patch("src.core.pause.is_paused", return_value=True):
        result = process_reflex("Build a dashboard")
    assert result.mode == "ALLOW"
