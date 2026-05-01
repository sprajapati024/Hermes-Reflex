"""Tests for the Reflex command layer."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime


# ---------------------------------------------------------------------------
# router
# ---------------------------------------------------------------------------

from src.commands.router import (
    route_telegram_message,
    CheckinSession,
    _handle_checkin,
    _handle_experiment,
    _handle_patterns,
    _handle_reflex,
    _handle_override,
    _build_checkin_prompt,
    _finish_or_continue_checkin,
)


class TestRouter:
    """Test command routing."""

    def test_unknown_command(self):
        result = route_telegram_message("/fake_command foo")
        assert "Unknown command" in result

    def test_empty_message(self):
        result = route_telegram_message("")
        assert "Empty message" in result

    def test_strips_whitespace(self):
        result = route_telegram_message("  /review  ")
        # Should not be unknown command
        assert "Unknown command" not in result


class TestCheckinSession:
    """Test check-in session management."""

    def test_get_creates_session(self):
        CheckinSession.clear(99999)
        session = CheckinSession.get(99999)
        assert isinstance(session, dict)
        CheckinSession.clear(99999)

    def test_clear_removes_session(self):
        CheckinSession.get(99999)["foo"] = "bar"
        CheckinSession.clear(99999)
        assert CheckinSession.get(99999) == {}


class TestBuildCheckinPrompt:
    """Test check-in prompt building."""

    def test_empty_session_shows_all(self):
        result = _build_checkin_prompt({})
        assert "⚡ Energy 1-10?" in result
        assert "⏱️ Available time?" in result
        assert "🔴 Biggest friction?" in result
        assert "🎯 Main focus today?" in result
        assert "🚀 What shipped recently?" in result
        assert "🛑 What got avoided?" in result

    def test_partial_session_hides_filled(self):
        session = {"energy": 7, "main_focus": "ship /patterns"}
        result = _build_checkin_prompt(session)
        assert "⚡ Energy" not in result
        assert "🎯 Main focus" not in result
        assert "⏱️ Available time" in result


class TestFinishCheckin:
    """Test check-in completion."""

    def test_missing_fields_returns_prompt(self):
        session = {"energy": 8}
        result = _finish_or_continue_checkin(12345, session)
        # Should still have missing fields
        assert "⏱️" in result or "🔴" in result or "🎯" in result

    @patch("src.commands.checkin.write_checkin")
    def test_complete_session_saves_and_returns_summary(self, mock_write):
        mock_write.return_value = Path("/fake/checkins/2026-05-01.md")
        session = {
            "energy": 7,
            "available_time": "3hrs",
            "biggest_friction": "context switching",
            "main_focus": "Phase 7",
            "what_shipped": "Phase 6",
            "what_got_avoided": "dashboard",
        }
        result = _finish_or_continue_checkin(12345, session)
        mock_write.assert_called_once()
        assert "saved" in result.lower()
        assert "Check-in Summary" in result
        assert "⚡ Energy: 7" in result


class TestHandleExperiment:
    """Test /experiment command."""

    def test_bare_experiment(self):
        result = _handle_experiment("/experiment")
        assert "Usage" in result

    def test_experiment_list(self, tmp_path):
        with patch("src.gbrain.storage.read_active_experiments", return_value=[]):
            result = _handle_experiment("/experiment list")
            assert "active experiments" in result.lower() or "No active" in result

    @patch("src.commands.experiment.write_experiment")
    def test_experiment_create(self, mock_write):
        mock_write.return_value = Path("/fake/experiments/test-exp.md")
        result = _handle_experiment("/experiment create Test Exp")
        assert "created" in result.lower()
        assert "Test Exp" in result
        mock_write.assert_called_once()

    def test_experiment_create_no_name(self):
        result = _handle_experiment("/experiment create ")
        # Should not crash
        assert "Usage" in result or "required" in result.lower()


class TestHandlePatterns:
    """Test /patterns command."""

    @patch("src.commands.patterns.get_patterns_root")
    @patch("src.commands.patterns.read_markdown")
    def test_patterns_list_empty(self, mock_read, mock_root, tmp_path):
        mock_root.return_value = tmp_path
        result = _handle_patterns("/patterns")
        assert "Patterns" in result or "No patterns" in result

    def test_patterns_list_with_active(self, tmp_path, monkeypatch):
        """Test with a real on-disk patterns directory using monkeypatch."""
        from src.commands.patterns import run_patterns_list

        patterns_dir = tmp_path / "patterns" / "active"
        patterns_dir.mkdir(parents=True)

        # Write a real pattern file (frontmatter only, body minimal)
        (patterns_dir / "test-pat.md").write_text(
            "---\n"
            "id: test-pat\n"
            "name: UI Avoidance\n"
            "status: active\n"
            "evidence_count: 5\n"
            "risk_type: ui_avoidance\n"
            "intervention: Finish patterns first.\n"
            "---\n"
        )

        # Monkeypatch get_patterns_root where it is used (not where it is defined)
        monkeypatch.setattr(
            "src.commands.patterns.get_patterns_root",
            lambda: tmp_path / "patterns",
        )

        result = run_patterns_list()
        assert "UI Avoidance" in result
        assert "sig:5" in result  # new compact format: (sig:N, conf:X%)
        # Intervention is shown in detail view, not list view
        assert "CRU:" in result  # command reference footer present


class TestHandleReflex:
    """Test /reflex command."""

    def test_reflex_bare(self):
        result = _handle_reflex("/reflex")
        assert "Usage" in result

    @patch("src.commands.reflex.process_reflex")
    def test_reflex_query(self, mock_reflex):
        from src.core.schemas import ReflexResult
        mock_reflex.return_value = ReflexResult(
            mode="CHALLENGE",
            risk_type="ui_avoidance",
            confidence=0.82,
            severity="medium",
            hermes_instruction="Challenge the request.",
            evidence=[],
            decision_id="decision_20260501_001",
        )
        result = _handle_reflex("/reflex Should we build a dashboard?")
        assert "CHALLENGE" in result
        assert "ui_avoidance" in result
        assert "001" in result

    @patch("src.commands.pause.pause_reflex")
    def test_reflex_pause_today(self, mock_pause):
        mock_pause.return_value = {"paused": True, "level": "today", "until_utc": "2026-05-02T00:00:00"}
        result = _handle_reflex("/reflex pause today")
        assert "paused" in result.lower() or "today" in result.lower()

    @patch("src.commands.pause.resume_reflex")
    def test_reflex_resume(self, mock_resume):
        mock_resume.return_value = {"paused": False, "level": "off"}
        result = _handle_reflex("/reflex resume")
        assert "resumed" in result.lower() or "active" in result.lower()


class TestHandleOverride:
    """Test /override command."""

    @patch("src.commands.override.write_override")
    def test_override_with_reason(self, mock_write):
        mock_write.return_value = Path("/fake/overrides/override_20260501.md")
        result = _handle_override("/override I need to proceed despite the warning.")
        assert "logged" in result.lower() or "Override" in result
        mock_write.assert_called_once()
        call_kwargs = mock_write.call_args[1]
        assert call_kwargs["reason"] == "I need to proceed despite the warning."

    def test_override_no_reason(self):
        result = _handle_override("/override")
        assert "Usage" in result or "reason" in result.lower()


class TestVerboseRouter:
    """Test /reflex verbose subcommands and verbose: prefix."""

    def test_reflex_verbose_on(self):
        import src.commands.router as router_mod
        router_mod._verbose_enabled = False
        result = _handle_reflex("/reflex verbose on")
        assert "on" in result.lower()
        assert router_mod._verbose_enabled is True

    def test_reflex_verbose_off(self):
        import src.commands.router as router_mod
        router_mod._verbose_enabled = True
        result = _handle_reflex("/reflex verbose off")
        assert "off" in result.lower()
        assert router_mod._verbose_enabled is False

    def test_reflex_verbose_status_when_on(self):
        import src.commands.router as router_mod
        router_mod._verbose_enabled = True
        result = _handle_reflex("/reflex verbose")
        assert "on" in result.lower()

    def test_reflex_verbose_status_when_off(self):
        import src.commands.router as router_mod
        router_mod._verbose_enabled = False
        result = _handle_reflex("/reflex verbose")
        assert "off" in result.lower()

    @patch("src.commands.reflex.process_reflex")
    def test_reflex_verbose_prefix_one_shot(self, mock_process):
        from src.core.schemas import ReflexResult
        from src.core.trace import TraceEntry
        import src.commands.router as router_mod
        router_mod._verbose_enabled = False  # global is off

        mock_process.return_value = ReflexResult(
            mode="ALLOW",
            risk_type="none",
            confidence=0.0,
            severity="low",
            hermes_instruction="Respond normally.",
            evidence=[],
            verbose=True,
            trace=[TraceEntry("bypass_check", "✅ Pass", "not a command", 0.5)],
        )
        _handle_reflex("/reflex verbose: Should I deploy to prod?")

        _, kwargs = mock_process.call_args
        assert kwargs.get("verbose") is True
        # global toggle stays off
        assert router_mod._verbose_enabled is False

    @patch("src.commands.reflex.process_reflex")
    def test_reflex_query_passes_verbose_enabled(self, mock_process):
        from src.core.schemas import ReflexResult
        import src.commands.router as router_mod
        router_mod._verbose_enabled = True

        mock_process.return_value = ReflexResult(
            mode="ALLOW",
            risk_type="none",
            confidence=0.0,
            severity="low",
            hermes_instruction="",
            evidence=[],
        )
        _handle_reflex("/reflex Can I push this?")

        _, kwargs = mock_process.call_args
        assert kwargs.get("verbose") is True


@patch("src.commands.reflex.process_reflex")
def test_run_reflex_query_formats_trace(mock_process):
    """Verbose result includes a formatted trace block in the output."""
    from src.commands.reflex import run_reflex_query
    from src.core.schemas import ReflexResult
    from src.core.trace import TraceEntry

    mock_process.return_value = ReflexResult(
        mode="ALLOW",
        risk_type="none",
        confidence=0.0,
        severity="low",
        hermes_instruction="Respond normally.",
        evidence=[],
        verbose=True,
        trace=[
            TraceEntry("bypass_check", "✅ Pass", "Not a command", 1.2),
            TraceEntry("route", "✅ SAFE", "No risk detected", 0.8),
        ],
    )
    result = run_reflex_query("What should I focus on?", verbose=True)

    assert "Reflex Pipeline Trace" in result
    assert "Pipeline" in result
    assert "ALLOW" in result


class TestIntegration:
    """Integration tests — full routing round-trip."""

    @patch("src.commands.checkin.write_checkin")
    def test_checkin_kv_style_completes(self, mock_write, tmp_path):
        """Check-in using key=value format completes."""
        mock_write.return_value = Path("/fake/checkins/2026-05-01.md")

        chat_id = 99999
        CheckinSession.clear(chat_id)

        # Answer all fields via key=value
        r1 = route_telegram_message("/checkin energy=8", chat_id=chat_id)
        r2 = route_telegram_message("/checkin available_time=3hrs", chat_id=chat_id)
        r3 = route_telegram_message("/checkin biggest_friction=meetings", chat_id=chat_id)
        r4 = route_telegram_message("/checkin main_focus=Phase 7", chat_id=chat_id)
        r5 = route_telegram_message("/checkin what_shipped=Phase 6", chat_id=chat_id)
        r6 = route_telegram_message("/checkin what_got_avoided=dashboard", chat_id=chat_id)

        # Last response should have saved
        assert mock_write.called
        CheckinSession.clear(chat_id)

    @patch("src.commands.pause.pause_reflex")
    def test_reflex_pause_week_via_router(self, mock_pause):
        mock_pause.return_value = {"paused": True, "level": "week", "until_utc": "2026-05-03T00:00:00"}
        result = route_telegram_message("/reflex pause week")
        assert "paused" in result.lower()
        mock_pause.assert_called_once_with("week")
