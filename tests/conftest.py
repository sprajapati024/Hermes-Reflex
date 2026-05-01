"""Shared pytest fixtures for the Hermes-Reflex test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path so `from src import ...` imports work
# regardless of how pytest was invoked.
_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


@pytest.fixture(autouse=True)
def clear_reflex_decision_cache():
    """Clear the in-process decision cache before every test.

    The cache is module-level state in src.core.middleware.  Without clearing
    it, a cached CHALLENGE result from one test can be returned by the next
    test that uses the same message text, causing spurious cache hits and
    missing write_decision / write_signal calls.
    """
    from src.core.middleware import _decision_cache, _cache_lock
    with _cache_lock:
        _decision_cache.clear()
    yield
    with _cache_lock:
        _decision_cache.clear()


@pytest.fixture(autouse=True)
def reset_verbose_state():
    """Reset the module-level verbose toggle in router between tests."""
    import src.commands.router as router_mod
    router_mod._verbose_enabled = False
    yield
    router_mod._verbose_enabled = False
