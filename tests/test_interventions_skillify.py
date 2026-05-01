"""Tests for interventions/skillify.py — Phase 10."""

from __future__ import annotations

import tempfile
import os
from datetime import datetime
from pathlib import Path

import pytest

fake_root = tempfile.mkdtemp()
os.environ["HERMES_REFLEX_GBRAIN_ROOT"] = fake_root

from src.interventions.skillify import (
    _make_skill_name,
    detect_skillify_candidates,
    create_candidate,
    list_candidates,
    approve_candidate,
    reject_candidate,
    scan_and_create_candidates,
    skillify_status_message,
    MIN_PATTERN_FIRES,
    MIN_USEFUL_INTERVENTIONS,
)


class TestMakeSkillName:
    def test_ui_avoidance(self):
        assert _make_skill_name("ui_avoidance") == "avoid-ui"

    def test_planning_loop(self):
        assert _make_skill_name("planning_loop") == "escape-planning"

    def test_overbuild_risk(self):
        assert _make_skill_name("overbuild_risk") == "prevent-overbuild"

    def test_unknown(self):
        result = _make_skill_name("some_weird_thing")
        # underscores are normalized to hyphens
        assert "some-weird-thing" in result
        assert result.startswith("handle-")


class TestDetectSkillifyCandidates:
    def test_empty_when_no_patterns(self):
        result = detect_skillify_candidates()
        assert result == []

    def test_respects_fire_threshold(self, tmp_gbrain_root):
        # Create pattern with fewer fires than threshold
        _write_pattern("test_pattern", "active", {"total_signals": 2})
        _write_intervention("test_pattern")
        _write_intervention("test_pattern")
        result = detect_skillify_candidates()
        assert result == []

    def test_respects_intervention_threshold(self, tmp_gbrain_root):
        # 5 fires but only 1 intervention
        _write_pattern("test_pattern", "active", {"total_signals": 5})
        _write_intervention("test_pattern")
        result = detect_skillify_candidates()
        assert result == []

    def test_detects_qualifying_pattern(self, tmp_gbrain_root):
        # 5 fires + 2 interventions = qualifies
        _write_pattern("ui_avoidance", "active", {
            "total_signals": 6,
            "name": "UI Avoidance",
            "intervention": "Ship reflex first.",
            "risk_type": "ui_avoidance",
        })
        _write_intervention("ui_avoidance")
        _write_intervention("ui_avoidance")
        result = detect_skillify_candidates()
        assert len(result) == 1
        assert result[0]["skill_name"] == "avoid-ui"
        assert result[0]["fire_count"] == 6


class TestCreateCandidate:
    def test_creates_file(self, tmp_gbrain_root):
        _write_pattern("test_pattern", "active", {"total_signals": 5})
        _write_intervention("test_pattern")
        _write_intervention("test_pattern")

        result = create_candidate(pattern_id="test_pattern")

        assert Path(result["path"]).exists()
        assert result["skill_name"] == "handle-test-pattern"
        assert "message" in result
        assert result["already_exists"] is False

    def test_idempotent_on_already_exists(self, tmp_gbrain_root):
        _write_pattern("test_pattern", "active", {"total_signals": 5})
        _write_intervention("test_pattern")
        _write_intervention("test_pattern")

        r1 = create_candidate(pattern_id="test_pattern")
        r2 = create_candidate(pattern_id="test_pattern")

        assert r1["already_exists"] is False
        assert r2["already_exists"] is True
        assert r1["path"] == r2["path"]

    def test_raises_if_pattern_not_found(self, tmp_gbrain_root):
        with pytest.raises(FileNotFoundError):
            create_candidate(pattern_id="nonexistent_pattern")

    def test_message_contains_approve_command(self, tmp_gbrain_root):
        _write_pattern("ui_avoidance", "active", {
            "total_signals": 5,
            "intervention": "No dashboard.",
            "risk_type": "ui_avoidance",
        })
        _write_intervention("ui_avoidance")
        _write_intervention("ui_avoidance")

        result = create_candidate(pattern_id="ui_avoidance")
        assert "/skillify approve" in result["message"]
        assert "/skillify reject" in result["message"]


class TestListCandidates:
    def test_empty_when_no_candidates(self, tmp_gbrain_root):
        result = list_candidates()
        assert result == []

    def test_lists_pending(self, tmp_gbrain_root):
        _write_pattern("p1", "active", {"total_signals": 5})
        _write_intervention("p1")
        _write_intervention("p1")
        create_candidate(pattern_id="p1")

        result = list_candidates(status="pending")
        assert len(result) == 1
        assert result[0]["skill_name"] == "handle-p1"

    def test_filters_by_status(self, tmp_gbrain_root):
        _write_pattern("p1", "active", {"total_signals": 5})
        _write_intervention("p1")
        _write_intervention("p1")
        create_candidate(pattern_id="p1")
        approve_candidate("handle-p1")

        pending = list_candidates(status="pending")
        approved = list_candidates(status="approved")
        assert pending == []
        assert len(approved) == 1


class TestApproveCandidate:
    def test_updates_status_to_approved(self, tmp_gbrain_root):
        _write_pattern("p1", "active", {"total_signals": 5})
        _write_intervention("p1")
        _write_intervention("p1")
        create_candidate(pattern_id="p1")

        approve_candidate("handle-p1")

        candidates = list_candidates(status="approved")
        assert len(candidates) == 1
        assert candidates[0]["skill_name"] == "handle-p1"

    def test_raises_if_not_found(self, tmp_gbrain_root):
        with pytest.raises(FileNotFoundError):
            approve_candidate("nonexistent-skill")


class TestRejectCandidate:
    def test_moves_to_rejected_dir(self, tmp_gbrain_root):
        _write_pattern("p1", "active", {"total_signals": 5})
        _write_intervention("p1")
        _write_intervention("p1")
        create_candidate(pattern_id="p1")

        reject_candidate("handle-p1")

        # Should be in rejected/ subdir
        from src.gbrain.paths import get_skillify_root
        rejected_dir = get_skillify_root() / "rejected"
        assert (rejected_dir / "handle-p1.md").exists()
        assert not (get_skillify_root() / "handle-p1.md").exists()


class TestScanAndCreateCandidates:
    def test_no_op_when_none_qualify(self, tmp_gbrain_root):
        result = scan_and_create_candidates()
        assert "No patterns met" in result

    def test_creates_candidates_for_qualifying(self, tmp_gbrain_root):
        _write_pattern("test_pattern", "active", {"total_signals": 5})
        _write_intervention("test_pattern")
        _write_intervention("test_pattern")

        result = scan_and_create_candidates()
        assert "new candidate" in result
        candidates = list_candidates()
        assert len(candidates) == 1


class TestSkillifyStatusMessage:
    def test_empty_state(self, tmp_gbrain_root):
        msg = skillify_status_message()
        assert "No pending candidates" in msg

    def test_shows_pending(self, tmp_gbrain_root):
        _write_pattern("test_pattern", "active", {"total_signals": 5})
        _write_intervention("test_pattern")
        _write_intervention("test_pattern")
        create_candidate(pattern_id="test_pattern")

        msg = skillify_status_message()
        assert "pending" in msg.lower()
        assert "handle-test-pattern" in msg


# --------------------------------------------------------------------------
# Fixtures / helpers
# --------------------------------------------------------------------------

@pytest.fixture
def tmp_gbrain_root(tmp_path, monkeypatch):
    """Set HERMES_REFLEX_GBRAIN_ROOT to a clean temp dir."""
    fake_root = tmp_path / "gbrain"
    fake_root.mkdir()
    monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", str(fake_root))
    return fake_root


def _write_pattern(pattern_id: str, status: str, data: dict) -> Path:
    """Write a minimal pattern file under the test gbrain root."""
    from src.gbrain.paths import get_pattern_path
    from src.gbrain.markdown import write_markdown

    defaults = {
        "id": pattern_id,
        "type": "pattern",
        "status": status,
        "name": pattern_id.replace("-", " ").replace("_", " ").title(),
        "intervention": "Test intervention.",
        "confidence": 0.75,
        "evidence_count": 1,
        "risk_type": pattern_id,
        "last_seen": datetime.now().date().isoformat(),
        "created_at": datetime.now().isoformat(),
        "total_signals": 0,
    }
    defaults.update(data)
    body = f"## Intervention\n{defaults.get('intervention', 'Test.')}\n"
    path = get_pattern_path(pattern_id, status)
    write_markdown(path, body, defaults)

    # Write real signal files so get_evidence_summary sees them
    fire_count = defaults.get("total_signals", 0)
    if fire_count > 0:
        for i in range(fire_count):
            _write_signal(pattern_id, days_ago=i * 2)  # spread signals over time

    return path


def _write_signal(risk_type: str, days_ago: int = 0) -> Path:
    """Write a minimal signal file for a risk type."""
    from src.gbrain.paths import get_signal_path
    from src.gbrain.markdown import write_markdown
    from datetime import timedelta
    import uuid

    data = {
        "id": f"signal_{uuid.uuid4().hex[:6]}",
        "type": "signal",
        "risk_type": risk_type,
        "signal_type": risk_type,
        "confidence": 0.75,
        "severity": "medium",
        "source": "test",
        "created_at": datetime.now().isoformat(),
    }
    body = f"## Evidence\nTest signal.\n"
    dt = datetime.now() - timedelta(days=days_ago)
    path = get_signal_path(dt)
    write_markdown(path, body, data)
    return path


def _write_intervention(pattern_id: str, days_ago: int = 1) -> Path:
    """Write a minimal intervention file for a pattern."""
    from src.gbrain.paths import get_intervention_path
    from src.gbrain.markdown import write_markdown
    from datetime import timedelta
    import uuid

    dt = datetime.now() - timedelta(days=days_ago)
    # Use unique sub-path to avoid overwriting when multiple calls have same dt
    uid = uuid.uuid4().hex[:6]
    data = {
        "id": f"intervention_{uid}",
        "type": "intervention",
        "decision_id": f"decision_{uid}",
        "risk_type": pattern_id,
        "mode": "CHALLENGE",
        "recommended_action": "Test intervention.",
        "created_at": dt.isoformat(),
    }
    body = f"## Recommended Action\nTest intervention.\n"
    # Write to a unique sub-path under the interventions dir to avoid overwrites
    int_root = get_intervention_path(dt).parent
    path = int_root / f"{dt.strftime('%Y-%m-%d')}_{uid}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(path, body, data)
    return path
