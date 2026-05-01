"""Tests for gbrain/paths.py"""

import os
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from src.gbrain import paths


class TestGetGBrainRoot:
    def test_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HERMES_REFLEX_GBRAIN_ROOT", raising=False)
        root = paths.get_gbrain_root()
        assert root.name == "gbrain"

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", td)
            assert paths.get_gbrain_root() == Path(td)


class TestReflexRoots:
    def test_reflex_root(self) -> None:
        assert "reflex" in str(paths.get_reflex_root())

    def test_sub_roots(self) -> None:
        for fn, name in [
            (paths.get_contracts_root, "contracts"),
            (paths.get_checkins_root, "checkins"),
            (paths.get_signals_root, "signals"),
            (paths.get_decisions_root, "decisions"),
            (paths.get_patterns_root, "patterns"),
            (paths.get_experiments_root, "experiments"),
            (paths.get_interventions_root, "interventions"),
            (paths.get_overrides_root, "overrides"),
            (paths.get_reviews_root, "reviews"),
            (paths.get_skillify_root, "skillify-candidates"),
            (paths.get_embeddings_root, "embeddings"),
        ]:
            assert name in str(fn())


class TestDatePaths:
    def test_checkin_path_creates_yyyymm_subdirs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", td)
            dt = datetime(2026, 5, 1)
            p = paths.get_checkin_path(dt)
            assert p.parent.name == "05"
            assert p.parent.parent.name == "2026"
            assert p.stem == "2026-05-01"

    def test_decision_path_deterministic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", td)
            dt = datetime(2026, 5, 1)
            p1 = paths.get_decision_path(dt)
            p2 = paths.get_decision_path(dt)
            assert p1 == p2


class TestExperimentPath:
    def test_active_status_subdir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", td)
            p = paths.get_experiment_path("no-dashboard-build", "active")
            assert p.parts[-3:-1] == ("experiments", "active")

    def test_experiment_path_preserves_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", td)
            p = paths.get_experiment_path("My Experiment", "active")
            assert "My Experiment.md" in str(p)


class TestEnsureDir:
    def test_creates_nested_dirs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("HERMES_REFLEX_GBRAIN_ROOT", td)
            deep = Path(td) / "a" / "b" / "c"
            result = paths.ensure_dir(deep / "file.md")
            assert result.parent.exists()
