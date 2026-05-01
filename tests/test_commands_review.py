"""Tests for /review command integration."""

from __future__ import annotations

from datetime import datetime

from src.commands.review import run_review
from src.gbrain.storage import ensure_reflex_structure, write_checkin, write_decision
from src.gbrain.markdown import read_markdown


def test_run_review_uses_phase9_weekly_generator(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", str(tmp_path))
    ensure_reflex_structure()

    now = datetime.now()
    write_checkin(
        energy=8,
        available_time="2 hours",
        biggest_friction="UI distraction",
        main_focus="Ship Reflex",
        what_shipped="Phase 9 weekly review generator",
        what_got_avoided="Dashboard planning",
        dt=now,
    )
    write_decision(
        mode="CHALLENGE",
        risk_type="ui_avoidance",
        confidence=0.88,
        severity="medium",
        evidence_ids=["exp_no_dashboard_build"],
        reason="Dashboard request conflicts with the active experiment.",
        recommended_action="Ship /patterns first.",
        dt=now,
    )

    message = run_review()

    assert "Weekly Reflex Review" in message
    assert "What Shipped" in message
    assert "Phase 9 weekly review generator" in message
    assert "Next Week" in message
    assert "Review saved" in message

    review_files = list((tmp_path / "reflex" / "reviews" / "weekly").rglob("*.md"))
    assert len(review_files) == 1
    data, body = read_markdown(review_files[0])
    assert data["review_type"] == "weekly"
    assert data["mode_counts"] == {"CHALLENGE": 1}
    assert "## What Shipped" in body
    assert "Phase 9 weekly review generator" in body
