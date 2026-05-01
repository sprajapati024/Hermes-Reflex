"""Shared pytest fixtures for the Hermes-Reflex test suite."""

from __future__ import annotations

import pytest


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
