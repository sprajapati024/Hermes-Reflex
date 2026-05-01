"""Tests for src/patterns/ — lifecycle, evidence, and detector."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.gbrain import storage
from src.gbrain.paths import get_reflex_root, get_patterns_root
from src.gbrain.markdown import read_markdown, write_markdown
from src.patterns import lifecycle, evidence, detector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a temp gbrain root for all pattern tests."""
    monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", str(tmp_path))
    storage.ensure_reflex_structure()
    return tmp_path


@pytest.fixture
def sample_pattern(temp_root: Path) -> str:
    """Create a basic candidate pattern and return its id."""
    return lifecycle.create_candidate(
        name="UI Avoidance",
        risk_type="ui_avoidance",
        matched_terms=["dashboard", "ui"],
        confidence=0.7,
        description="Adding UI work when told not to.",
    )


# ---------------------------------------------------------------------------
# lifecycle.create_candidate
# ---------------------------------------------------------------------------

class TestCreateCandidate:
    def test_creates_file_in_candidate_dir(
        self, temp_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pid = lifecycle.create_candidate(
            name="Planning Loop",
            risk_type="planning_loop",
            matched_terms=["rethink"],
            confidence=0.6,
        )
        assert pid == "planning-loop"
        patterns_dir = get_patterns_root() / "candidate"
        assert (patterns_dir / f"{pid}.md").exists()

    def test_returns_pattern_id(self, temp_root: Path) -> None:
        pid = lifecycle.create_candidate(
            name="Test Pattern",
            risk_type="test-pattern",
            matched_terms=[],
            confidence=0.5,
        )
        assert pid == "test-pattern"

    def test_idempotent_on_duplicate(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        # Calling again with same risk_type should update, not error
        pid2 = lifecycle.create_candidate(
            name="UI Avoidance",
            risk_type="ui_avoidance",
            matched_terms=["dashboard"],
            confidence=0.8,
        )
        assert pid2 == sample_pattern
        # Verify file still exists
        assert (get_patterns_root() / "candidate" / f"{sample_pattern}.md").exists()

    def test_sets_correct_frontmatter(
        self, temp_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pid = lifecycle.create_candidate(
            name="Overbuild",
            risk_type="overbuild_risk",
            matched_terms=["microservices"],
            confidence=0.75,
            description="Infrastructure cosplay.",
        )
        data, body = read_markdown(get_patterns_root() / "candidate" / f"{pid}.md")
        assert data["id"] == pid
        assert data["status"] == "candidate"
        assert data["risk_type"] == "overbuild_risk"
        assert data["confidence"] == 0.75
        assert data["evidence_count"] == 1


# ---------------------------------------------------------------------------
# lifecycle.get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_returns_candidate_for_new_pattern(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        assert lifecycle.get_status(sample_pattern) == "candidate"

    def test_returns_none_for_unknown(self, temp_root: Path) -> None:
        assert lifecycle.get_status("nonexistent-pattern") is None


# ---------------------------------------------------------------------------
# lifecycle.promote
# ---------------------------------------------------------------------------

class TestPromote:
    def test_candidate_to_watching(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        new_status = lifecycle.promote(sample_pattern)
        assert new_status == "watching"
        assert lifecycle.get_status(sample_pattern) == "watching"

    def test_watching_to_active(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        lifecycle.promote(sample_pattern)  # candidate → watching
        new_status = lifecycle.promote(sample_pattern)  # watching → active
        assert new_status == "active"
        assert lifecycle.get_status(sample_pattern) == "active"

    def test_active_promotes_to_retired(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        lifecycle.promote(sample_pattern)  # candidate → watching
        result = lifecycle.promote(sample_pattern)  # watching → active
        assert result == "active"
        # Promoting an active pattern transitions it to retired (valid transition)
        result = lifecycle.promote(sample_pattern)  # active → retired
        assert result == "retired"
        assert lifecycle.get_status(sample_pattern) == "retired"

    def test_retired_cannot_promote(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        lifecycle.retire(sample_pattern)
        with pytest.raises(FileNotFoundError, match="not found"):
            lifecycle.promote(sample_pattern)


# ---------------------------------------------------------------------------
# lifecycle.demote
# ---------------------------------------------------------------------------

class TestDemote:
    def test_watching_to_candidate(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        lifecycle.promote(sample_pattern)  # to watching
        new_status = lifecycle.demote(sample_pattern)
        assert new_status == "candidate"
        assert lifecycle.get_status(sample_pattern) == "candidate"

    def test_active_to_watching(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        lifecycle.promote(sample_pattern)
        lifecycle.promote(sample_pattern)  # to active
        new_status = lifecycle.demote(sample_pattern)
        assert new_status == "watching"
        assert lifecycle.get_status(sample_pattern) == "watching"

    def test_candidate_cannot_demote(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        with pytest.raises(ValueError, match="no valid transitions"):
            lifecycle.demote(sample_pattern)


# ---------------------------------------------------------------------------
# lifecycle.retire
# ---------------------------------------------------------------------------

class TestRetire:
    def test_retires_active_pattern(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        lifecycle.promote(sample_pattern)
        lifecycle.promote(sample_pattern)  # active
        result = lifecycle.retire(sample_pattern)
        assert result == "retired"
        assert lifecycle.get_status(sample_pattern) == "retired"
        # File should be moved to retired/
        assert (get_patterns_root() / "retired" / f"{sample_pattern}.md").exists()

    def test_retires_candidate(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        result = lifecycle.retire(sample_pattern)
        assert result == "retired"
        assert lifecycle.get_status(sample_pattern) == "retired"

    def test_retired_is_idempotent(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        lifecycle.retire(sample_pattern)
        # Calling retire again should work (already retired)
        result = lifecycle.retire(sample_pattern)
        assert result == "retired"

    def test_nonexistent_raises(
        self, temp_root: Path
    ) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            lifecycle.retire("totally-made-up-pattern")


# ---------------------------------------------------------------------------
# lifecycle.get_promotion_advice
# ---------------------------------------------------------------------------

class TestPromotionAdvice:
    def test_candidate_advice(self, temp_root: Path, sample_pattern: str) -> None:
        advice = lifecycle.get_promotion_advice(sample_pattern)
        assert advice["current_status"] == "candidate"
        assert advice["next_status"] == "watching"
        assert "signals_needed" in advice
        assert isinstance(advice["blockers"], list)

    def test_watching_advice(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        lifecycle.promote(sample_pattern)
        advice = lifecycle.get_promotion_advice(sample_pattern)
        assert advice["current_status"] == "watching"
        assert advice["next_status"] == "active"

    def test_active_advice(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        lifecycle.promote(sample_pattern)
        lifecycle.promote(sample_pattern)
        advice = lifecycle.get_promotion_advice(sample_pattern)
        assert advice["current_status"] == "active"
        assert advice["next_status"] == "retired"

    def test_retired_advice(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        lifecycle.retire(sample_pattern)
        advice = lifecycle.get_promotion_advice(sample_pattern)
        assert advice["current_status"] == "retired"
        assert advice["next_status"] is None
        assert "already retired" in advice["blockers"][0]


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------

class TestEvidenceSummary:
    def test_new_pattern_has_no_signals(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        summary = evidence.get_evidence_summary(sample_pattern)
        assert summary["signals_in_window"] == 0
        assert summary["total_signals"] == 0
        assert summary["candidate_threshold_met"] is False

    def test_has_intervention_false_when_no_interventions(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        summary = evidence.get_evidence_summary(sample_pattern)
        assert summary["has_intervention"] is False

    def test_days_since_firing_none_for_new_pattern(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        summary = evidence.get_evidence_summary(sample_pattern)
        assert summary["days_since_firing"] is None


# ---------------------------------------------------------------------------
# commands/patterns.py
# ---------------------------------------------------------------------------

class TestPatternsCommand:
    def test_list_empty(self, temp_root: Path) -> None:
        from src.commands.patterns import _handle_list
        result = _handle_list()
        assert "No patterns yet" in result

    def test_list_shows_candidate(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        from src.commands.patterns import _handle_list
        result = _handle_list()
        assert sample_pattern in result
        assert "Candidate" in result

    def test_add_creates_candidate(
        self, temp_root: Path
    ) -> None:
        from src.commands.patterns import _handle_add
        result = _handle_add("planning-loop", "Planning Loop", None)
        assert "added as *candidate*" in result
        assert lifecycle.get_status("planning-loop") == "candidate"

    def test_add_idempotent(
        self, temp_root: Path
    ) -> None:
        from src.commands.patterns import _handle_add
        _handle_add("test-pattern", "Test", None)
        result = _handle_add("test-pattern", "Test", None)
        # Should not raise, just update
        assert "added" in result.lower() or "pattern" in result.lower()

    def test_promote_command(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        from src.commands.patterns import _handle_promote
        result = _handle_promote(sample_pattern)
        assert "→ *watching*" in result

    def test_demote_command(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        from src.commands.patterns import _handle_demote
        lifecycle.promote(sample_pattern)
        result = _handle_demote(sample_pattern)
        assert "→ *candidate*" in result

    def test_retire_command(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        from src.commands.patterns import _handle_retire
        result = _handle_retire(sample_pattern)
        assert "retired" in result.lower()

    def test_advice_command(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        from src.commands.patterns import _handle_advice
        result = _handle_advice(sample_pattern)
        assert "Promotion Advice" in result
        assert "candidate" in result.lower()

    def test_detail_unknown_pattern(
        self, temp_root: Path
    ) -> None:
        from src.commands.patterns import _handle_detail
        result = _handle_detail("totally-fake")
        assert "not found" in result.lower()

    def test_detail_existing_pattern(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        from src.commands.patterns import _handle_detail
        result = _handle_detail(sample_pattern)
        assert sample_pattern in result or "UI Avoidance" in result

    def test_run_patterns_command_add(
        self, temp_root: Path
    ) -> None:
        from src.commands.patterns import run_patterns_command
        result = run_patterns_command("/patterns add overbuild-risk")
        assert "added" in result.lower()

    def test_run_patterns_command_promote(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        from src.commands.patterns import run_patterns_command
        result = run_patterns_command(f"/patterns promote {sample_pattern}")
        assert "watching" in result.lower()

    def test_run_patterns_command_retire(
        self, temp_root: Path, sample_pattern: str
    ) -> None:
        from src.commands.patterns import run_patterns_command
        result = run_patterns_command(f"/patterns retire {sample_pattern}")
        assert "retired" in result.lower()
