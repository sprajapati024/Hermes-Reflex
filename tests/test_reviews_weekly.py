"""Tests for reviews/weekly.py — Phase 9."""

from __future__ import annotations

import tempfile
import os
from datetime import datetime
from pathlib import Path

import pytest

# Set up a fake GBRAIN root before importing anything
fake_root = tempfile.mkdtemp()
os.environ["HERMES_REFLEX_GBRAIN_ROOT"] = fake_root

from src.reviews.weekly import (
    _extract_shipped_from_checkins,
    _extract_stalled_from_checkins,
    _count_modes,
    _count_patterns_fired,
    _generate_stop_doing,
    _generate_next_week_recommendation,
    _build_what_shipped_section,
    _build_what_stalled_section,
    generate_weekly_review,
)


class TestExtractShipped:
    def test_extracts_what_shipped_key(self):
        checkins = [{"what_shipped": "Finished Phase 9 tests"}]
        result = _extract_shipped_from_checkins(checkins)
        assert result == ["Finished Phase 9 tests"]

    def test_extracts_dash_version(self):
        checkins = [{"what-shipped": "Shipped dashboard"}]
        result = _extract_shipped_from_checkins(checkins)
        assert result == ["Shipped dashboard"]

    def test_empty_if_missing(self):
        assert _extract_shipped_from_checkins([{}]) == []
        assert _extract_shipped_from_checkins([]) == []

    def test_deduplication_in_section(self):
        # Deduplication is done in _build_what_shipped_section, not the extractor
        from src.reviews.weekly import _build_what_shipped_section
        raw = ["Did the thing", "did the thing", "Did the thing"]
        section = _build_what_shipped_section(raw)
        # Should appear once in output despite case-duplicate
        assert section.count("- Did the thing") == 1
        assert section.count("Did the thing") == 1

    def test_strips_whitespace(self):
        checkins = [{"what_shipped": "  lots of space  "}]
        result = _extract_shipped_from_checkins(checkins)
        assert result == ["lots of space"]


class TestExtractStalled:
    def test_extracts_what_got_avoided(self):
        checkins = [{"what_got_avoided": "Dashboard planning"}]
        result = _extract_stalled_from_checkins(checkins)
        assert result == ["Dashboard planning"]

    def test_extracts_dash_version(self):
        checkins = [{"what-got-avoided": "Frontend work"}]
        result = _extract_stalled_from_checkins(checkins)
        assert result == ["Frontend work"]

    def test_empty_if_missing(self):
        assert _extract_stalled_from_checkins([{}]) == []
        assert _extract_stalled_from_checkins([]) == []


class TestCountModes:
    def test_counts_all_modes(self):
        decisions = [
            {"mode": "CHALLENGE"},
            {"mode": "CHALLENGE"},
            {"mode": "ALLOW"},
            {"mode": "NOTE"},
        ]
        result = _count_modes(decisions)
        assert result == {"CHALLENGE": 2, "ALLOW": 1, "NOTE": 1}

    def test_defaults_allow(self):
        decisions = [{}, {"mode": "REQUIRE_OVERRIDE"}]
        result = _count_modes(decisions)
        assert result == {"ALLOW": 1, "REQUIRE_OVERRIDE": 1}


class TestCountPatternsFired:
    def test_counts_by_risk_type(self):
        signals = [
            {"risk_type": "ui_avoidance"},
            {"risk_type": "ui_avoidance"},
            {"risk_type": "planning_loop"},
        ]
        result = _count_patterns_fired(signals)
        assert result == {"ui_avoidance": 2, "planning_loop": 1}

    def test_falls_back_to_signal_type(self):
        signals = [{"signal_type": "scope_creep"}]
        result = _count_patterns_fired(signals)
        assert result == {"scope_creep": 1}

    def test_unknown_for_empty(self):
        assert _count_patterns_fired([]) == {}


class TestBuildWhatShippedSection:
    def test_empty_message(self):
        text = _build_what_shipped_section([])
        assert "Nothing recorded" in text

    def test_bullets_for_items(self):
        text = _build_what_shipped_section(["Did thing", "Shipped feature"])
        assert "- Did thing" in text
        assert "- Shipped feature" in text


class TestBuildWhatStalledSection:
    def test_empty_message(self):
        text = _build_what_stalled_section([])
        assert "Nothing recorded" in text

    def test_bullets_for_items(self):
        text = _build_what_stalled_section(["Dashboard planning"])
        assert "- Dashboard planning" in text


class TestGenerateStopDoing:
    def test_many_overrides(self):
        overrides = [{"reason": "a"}, {"reason": "b"}, {"reason": "c"}]
        result = _generate_stop_doing(overrides, [], [])
        assert "override" in result.lower()

    def test_many_stalled(self):
        stalled = ["item1", "item2", "item3"]
        result = _generate_stop_doing([], stalled, [])
        assert "stalled" in result.lower()

    def test_repeated_pattern(self):
        signals = [
            {"risk_type": "planning_loop"},
            {"risk_type": "planning_loop"},
            {"risk_type": "planning_loop"},
        ]
        result = _generate_stop_doing([], [], signals)
        assert "planning_loop" in result.lower()

    def test_default(self):
        result = _generate_stop_doing([], [], [])
        assert len(result) > 0


class TestGenerateNextWeekRecommendation:
    def test_one_experiment(self):
        experiments = [{"name": "No Dashboard Build"}]
        result = _generate_next_week_recommendation(experiments, [], [], [])
        assert "No Dashboard Build" in result

    def test_multiple_experiments(self):
        experiments = [{"name": "Exp A"}, {"name": "Exp B"}]
        result = _generate_next_week_recommendation(experiments, [], [], [])
        assert "Exp A" in result

    def test_high_override_count(self):
        overrides = [{"reason": "a"}, {"reason": "b"}]
        result = _generate_next_week_recommendation([], [], [], overrides)
        assert "override" in result.lower()

    def test_no_non_allow_decisions(self):
        decisions = [{"mode": "ALLOW"}, {"mode": "ALLOW"}, {"mode": "ALLOW"}, {"mode": "ALLOW"}]
        result = _generate_next_week_recommendation([], decisions, [], [])
        assert "reflex" in result.lower()

    def test_default_recommendation(self):
        result = _generate_next_week_recommendation([], [], [], [])
        assert len(result) > 0


class TestGenerateWeeklyReview:
    def test_creates_review_file(self, tmp_gbrain_root):
        result = generate_weekly_review()
        assert Path(result["path"]).exists()
        assert "message" in result
        assert "sections" in result

    def test_review_file_has_frontmatter(self, tmp_gbrain_root):
        result = generate_weekly_review()
        content = Path(result["path"]).read_text()
        assert "---" in content
        assert "type: review" in content

    def test_message_contains_week(self, tmp_gbrain_root):
        now = datetime.now()
        year, week_num = now.isocalendar()[:2]
        result = generate_weekly_review()
        assert f"{year}-W{week_num:02d}" in result["message"]

    def test_sections_complete(self, tmp_gbrain_root):
        result = generate_weekly_review()
        sections = result["sections"]
        required_keys = [
            "what_shipped",
            "what_stalled",
            "patterns_fired",
            "mode_counts",
            "interventions_accepted",
            "total_decisions",
            "overrides_count",
            "experiment_results",
            "next_week_recommendation",
            "stop_doing",
        ]
        for key in required_keys:
            assert key in sections, f"Missing section: {key}"

    def test_week_file_path_is_iso_week(self, tmp_gbrain_root):
        now = datetime.now()
        year, week_num = now.isocalendar()[:2]
        result = generate_weekly_review()
        path = Path(result["path"])
        assert f"{year}-W{week_num:02d}" in path.name

    def test_idempotent(self, tmp_gbrain_root):
        # Two calls to same week should overwrite cleanly
        result1 = generate_weekly_review()
        result2 = generate_weekly_review()
        assert result1["path"] == result2["path"]
        assert Path(result1["path"]).exists()


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def tmp_gbrain_root(tmp_path, monkeypatch):
    """Set HERMES_REFLEX_GBRAIN_ROOT to a clean temp dir."""
    fake_root = tmp_path / "gbrain"
    fake_root.mkdir()
    monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", str(fake_root))
    return fake_root
