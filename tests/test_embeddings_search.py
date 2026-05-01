"""Tests for src/embeddings/search.py."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


class TestSearchReflexMemory:
    """Test the main search_reflex_memory() function."""

    def test_search_reflex_memory_calls_embed_text(self):
        """search_reflex_memory embeds the query before searching."""
        mock_vector = [0.1] * 1536

        with patch("src.embeddings.search.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.embed_text.return_value = mock_vector
            mock_get_client.return_value = mock_client

            with patch("src.embeddings.search.search_by_vector", return_value=[]) as mock_search:
                with patch("src.embeddings.search._keyword_fallback", return_value=[]):
                    from src.embeddings.search import search_reflex_memory
                    result = search_reflex_memory("test query", top_k=5)

                    mock_client.embed_text.assert_called_once_with("test query")
                    mock_search.assert_called_once()

    def test_search_reflex_memory_returns_results(self):
        mock_vector = [0.1] * 1536
        mock_results = [
            {"id": "chunk1", "path": "/tmp/test.md", "type": "pattern", "score": 0.85, "title": "Test", "content": "Content"}
        ]

        with patch("src.embeddings.search.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.embed_text.return_value = mock_vector
            mock_get_client.return_value = mock_client

            with patch("src.embeddings.search.search_by_vector", return_value=mock_results):
                from src.embeddings.search import search_reflex_memory
                result = search_reflex_memory("test query")
                assert len(result) == 1
                assert result[0]["score"] == 0.85


class TestKeywordFallback:
    """Test keyword fallback when vector search returns nothing."""

    def test_keyword_fallback_no_query_words(self):
        """Empty query returns empty list."""
        with patch("src.embeddings.search._get_all_indexed_docs", return_value=[]):
            from src.embeddings.search import _keyword_fallback
            result = _keyword_fallback("", top_k=5)
            assert result == []

    def test_keyword_fallback_matches_title(self):
        doc = {"id": "d1", "title": "My Pattern", "content": "Body text", "path": "/tmp/p.md"}
        with patch("src.embeddings.search._get_all_indexed_docs", return_value=[doc]):
            from src.embeddings.search import _keyword_fallback
            result = _keyword_fallback("pattern", top_k=5)
            assert len(result) == 1
            assert result[0]["id"] == "d1"

    def test_keyword_fallback_matches_content(self):
        doc = {"id": "d2", "title": "Untitled", "content": "Reflex middleware is working", "path": "/tmp/d.md"}
        with patch("src.embeddings.search._get_all_indexed_docs", return_value=[doc]):
            from src.embeddings.search import _keyword_fallback
            result = _keyword_fallback("middleware", top_k=5)
            assert len(result) == 1

    def test_keyword_fallback_no_match(self):
        doc = {"id": "d3", "title": "Different", "content": "Something else", "path": "/tmp/x.md"}
        with patch("src.embeddings.search._get_all_indexed_docs", return_value=[doc]):
            from src.embeddings.search import _keyword_fallback
            result = _keyword_fallback("xyzzy", top_k=5)
            assert result == []


class TestRetrieveForContext:
    """Test retrieve_for_context."""

    def test_retrieve_for_context_uses_lower_min_score(self):
        """retrieve_for_context uses min_score=0.5 vs default 0.65."""
        mock_vector = [0.1] * 1536

        with patch("src.embeddings.search.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.embed_text.return_value = mock_vector
            mock_get_client.return_value = mock_client

            with patch("src.embeddings.search.search_by_vector", return_value=[]) as mock_search:
                with patch("src.embeddings.search._keyword_fallback", return_value=[]):
                    from src.embeddings.search import retrieve_for_context
                    retrieve_for_context("test", allowed_types=["pattern"])
                    mock_search.assert_called_once()
                    call_kwargs = mock_search.call_args.kwargs
                    assert call_kwargs["min_score"] == 0.5
