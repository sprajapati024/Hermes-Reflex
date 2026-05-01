"""Tests for YAML rule loading in src/core/rule_engine.py."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from src.core.rule_engine import load_yaml_rules, evaluate_rules, _compile_yaml_term


# ---------------------------------------------------------------------------
# _compile_yaml_term
# ---------------------------------------------------------------------------

def test_compile_plain_term_adds_word_boundaries():
    pattern = _compile_yaml_term("dashboard")
    assert pattern is not None
    assert pattern.search("add a dashboard here") is not None
    assert pattern.search("dashboardX") is None  # not a whole word


def test_compile_plain_term_case_insensitive():
    pattern = _compile_yaml_term("Dashboard")
    assert pattern is not None
    assert pattern.search("DASHBOARD") is not None


def test_compile_regex_term_used_as_is():
    pattern = _compile_yaml_term(r"\bfoo\s+bar\b")
    assert pattern is not None
    assert pattern.search("foo bar") is not None
    assert pattern.search("foobar") is None


def test_compile_invalid_regex_returns_none():
    # Unmatched bracket is invalid regex
    result = _compile_yaml_term(r"[unclosed")
    assert result is None


# ---------------------------------------------------------------------------
# load_yaml_rules — directory handling
# ---------------------------------------------------------------------------

def test_load_yaml_rules_returns_empty_for_missing_dir():
    result = load_yaml_rules(rules_dir="/nonexistent/path/that/cannot/exist")
    assert result == {}


def test_load_yaml_rules_returns_empty_for_none_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_REFLEX_RULES_DIR", str(tmp_path / "no_such_dir"))
    result = load_yaml_rules()
    assert result == {}


def test_load_yaml_rules_loads_valid_rule(tmp_path):
    rule_file = tmp_path / "test_scope_creep.yaml"
    rule_file.write_text(textwrap.dedent("""\
        id: test_scope_creep
        severity: medium
        mode: CHALLENGE
        enabled: true
        terms:
          - build another app
          - second project
    """))

    rules = load_yaml_rules(rules_dir=str(tmp_path))

    assert "test_scope_creep" in rules
    rule = rules["test_scope_creep"]
    assert rule["severity"] == "MEDIUM"
    assert len(rule["_compiled"]) == 2


def test_load_yaml_rules_skips_disabled_rules(tmp_path):
    rule_file = tmp_path / "disabled_rule.yaml"
    rule_file.write_text(textwrap.dedent("""\
        id: disabled_rule
        severity: high
        mode: REQUIRE_OVERRIDE
        enabled: false
        terms:
          - some term
    """))

    rules = load_yaml_rules(rules_dir=str(tmp_path))
    assert "disabled_rule" not in rules


def test_load_yaml_rules_ignores_non_yaml_files(tmp_path):
    (tmp_path / "not_a_rule.txt").write_text("id: fake\nterms:\n  - something\n")
    (tmp_path / "also_not.json").write_text('{"id": "fake"}')
    rules = load_yaml_rules(rules_dir=str(tmp_path))
    assert len(rules) == 0


def test_load_yaml_rules_tolerates_malformed_file(tmp_path):
    (tmp_path / "bad.yaml").write_text(": : : invalid yaml { ]")
    (tmp_path / "good.yaml").write_text(textwrap.dedent("""\
        id: good_rule
        severity: medium
        enabled: true
        terms:
          - good term
    """))
    rules = load_yaml_rules(rules_dir=str(tmp_path))
    assert "good_rule" in rules


def test_load_yaml_rules_uses_filename_as_id_when_missing(tmp_path):
    (tmp_path / "my_custom_rule.yaml").write_text(textwrap.dedent("""\
        severity: medium
        enabled: true
        terms:
          - custom term
    """))
    rules = load_yaml_rules(rules_dir=str(tmp_path))
    assert "my_custom_rule" in rules


def test_load_yaml_rules_high_severity(tmp_path):
    (tmp_path / "high_rule.yaml").write_text(textwrap.dedent("""\
        id: high_rule
        severity: high
        enabled: true
        terms:
          - dangerous term
    """))
    rules = load_yaml_rules(rules_dir=str(tmp_path))
    assert rules["high_rule"]["severity"] == "HIGH"


# ---------------------------------------------------------------------------
# Integration — YAML rules fire in evaluate_rules()
# ---------------------------------------------------------------------------

def test_evaluate_rules_matches_yaml_rule(tmp_path, monkeypatch):
    """A YAML rule should be detected by evaluate_rules after loading."""
    (tmp_path / "test_scope_creep.yaml").write_text(textwrap.dedent("""\
        id: test_scope_creep
        severity: medium
        mode: CHALLENGE
        enabled: true
        terms:
          - build another app
    """))

    # Reload active rules from the tmp directory
    import src.core.rule_engine as re_mod
    original_active = re_mod._ACTIVE_RULES.copy()
    try:
        yaml_rules = load_yaml_rules(rules_dir=str(tmp_path))
        re_mod._ACTIVE_RULES.update(yaml_rules)

        result = evaluate_rules("Should we build another app for this?")
        assert "test_scope_creep" in result.risk_flags
        assert result.recommended_mode == "CHALLENGE"
    finally:
        re_mod._ACTIVE_RULES.clear()
        re_mod._ACTIVE_RULES.update(original_active)


def test_yaml_rule_overrides_builtin(tmp_path):
    """A YAML rule with the same ID as a built-in should override it."""
    # Override ui_avoidance to CHALLENGE instead of REQUIRE_OVERRIDE
    (tmp_path / "ui_avoidance.yaml").write_text(textwrap.dedent("""\
        id: ui_avoidance
        severity: medium
        mode: CHALLENGE
        enabled: true
        terms:
          - dashboard
    """))

    import src.core.rule_engine as re_mod
    original_active = re_mod._ACTIVE_RULES.copy()
    try:
        yaml_rules = load_yaml_rules(rules_dir=str(tmp_path))
        re_mod._ACTIVE_RULES.update(yaml_rules)

        result = evaluate_rules("Let's add a dashboard")
        assert "ui_avoidance" in result.risk_flags
        assert result.recommended_mode == "CHALLENGE"  # overridden from REQUIRE_OVERRIDE
    finally:
        re_mod._ACTIVE_RULES.clear()
        re_mod._ACTIVE_RULES.update(original_active)


def test_builtin_rules_remain_as_fallback(tmp_path):
    """Built-in rules must still fire even when an empty YAML dir is provided."""
    import src.core.rule_engine as re_mod
    original_active = re_mod._ACTIVE_RULES.copy()
    try:
        yaml_rules = load_yaml_rules(rules_dir=str(tmp_path))  # empty dir
        re_mod._ACTIVE_RULES.update(yaml_rules)

        result = evaluate_rules("Let's add a dashboard")
        assert "ui_avoidance" in result.risk_flags
    finally:
        re_mod._ACTIVE_RULES.clear()
        re_mod._ACTIVE_RULES.update(original_active)


def test_env_var_rules_dir(tmp_path, monkeypatch):
    """HERMES_REFLEX_RULES_DIR env var should control the default rules dir."""
    (tmp_path / "env_rule.yaml").write_text(textwrap.dedent("""\
        id: env_rule
        severity: medium
        enabled: true
        terms:
          - env test term
    """))

    monkeypatch.setenv("HERMES_REFLEX_RULES_DIR", str(tmp_path))
    rules = load_yaml_rules()  # no explicit dir — should use env var
    assert "env_rule" in rules
