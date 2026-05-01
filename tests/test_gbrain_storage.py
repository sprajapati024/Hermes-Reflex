"""Tests for gbrain/storage.py"""

import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.gbrain import storage
from src.gbrain.paths import get_reflex_root


class TestEnsureReflexStructure:
    def test_creates_all_subdirs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", td)
            root = storage.ensure_reflex_structure()
            expected_subs = [
                "contracts",
                "checkins",
                "signals",
                "decisions",
                "patterns/candidate",
                "patterns/watching",
                "patterns/active",
                "patterns/retired",
                "experiments/planned",
                "experiments/active",
                "experiments/completed",
                "experiments/abandoned",
                "interventions",
                "overrides",
                "reviews/weekly",
                "reviews/monthly",
                "skillify-candidates",
                "embeddings",
            ]
            for sub in expected_subs:
                assert (root / sub).is_dir(), f"Missing: {sub}"


class TestWriteCheckin:
    def test_writes_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", td)
            storage.ensure_reflex_structure()
            path = storage.write_checkin(
                energy=7,
                available_time="90 minutes",
                main_focus="Hermes Reflex",
            )
            assert path.exists()
            data, body = storage.read_markdown(path)
            assert data["type"] == "checkin"
            assert data["energy"] == 7
            assert "90 minutes" in body


class TestWriteExperiment:
    def test_roundtrip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", td)
            storage.ensure_reflex_structure()
            path = storage.write_experiment(
                name="No Dashboard Build",
                hypothesis="Avoiding frontend work speeds up core loop shipping.",
                rules=["No dashboard", "No frontend"],
                metric="Working commands shipped.",
                success_criteria="4 commands in 7 days.",
            )
            assert path.exists()
            data, _ = storage.read_experiment("no-dashboard-build", "active")
            assert data["name"] == "No Dashboard Build"
            assert data["status"] == "active"


class TestReadActiveExperiments:
    def test_empty_when_no_files(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", td)
            result = storage.read_active_experiments()
            assert result == []


class TestWriteDecision:
    def test_writes_with_correct_id_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", td)
            storage.ensure_reflex_structure()
            path = storage.write_decision(
                mode="CHALLENGE",
                risk_type="ui_avoidance",
                confidence=0.86,
                severity="medium",
                evidence_ids=["pattern_ui_avoidance"],
                reason="Conflicts with no-dashboard constraint.",
                recommended_action="Finish /patterns first.",
            )
            assert path.exists()
            data, body = storage.read_markdown(path)
            assert data["mode"] == "CHALLENGE"
            assert data["id"].startswith("decision_")


class TestWriteOperatingContract:
    def test_roundtrip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", td)
            storage.ensure_reflex_structure()
            path = storage.write_operating_contract(
                active_goal="Ship Hermes Reflex v1.",
                constraints=["No dashboard", "No frontend"],
                reflex_authority="Hermes Reflex may challenge requests that conflict with this contract.",
                override_policy="Overrides must be logged.",
            )
            data, body = storage.read_current_contract()
            assert data["status"] == "active"
            assert "No dashboard" in body


class TestWriteOverride:
    def test_writes_and_reads_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", td)
            storage.ensure_reflex_structure()
            path = storage.write_override(
                decision_id="decision_20260501_001",
                reason="User explicitly chose to continue.",
                original_mode="REQUIRE_OVERRIDE",
            )
            assert path.exists()
            data, _ = storage.read_markdown(path)
            assert data["type"] == "override"
            assert data["original_mode"] == "REQUIRE_OVERRIDE"
