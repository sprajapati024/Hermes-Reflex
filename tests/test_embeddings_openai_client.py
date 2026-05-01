"""Tests for src/embeddings/openai_client.py."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


class TestEmbeddingClientConfig:
    """Test that config is loaded correctly."""

    def test_model_defaults_to_text_embedding_3_small(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-123"}):
            # Mock the config to return defaults
            with patch("src.embeddings.openai_client._load_config") as mock_cfg:
                mock_cfg.return_value = {"openai_embeddings": {"model": "text-embedding-3-small", "dimensions": 1536, "batch_size": 100}}
                from src.embeddings.openai_client import get_embedding_config
                cfg = get_embedding_config()
                assert cfg["model"] == "text-embedding-3-small"
                assert cfg["dimensions"] == 1536
                assert cfg["batch_size"] == 100


class TestEmbedBatch:
    """Test batch embedding calls."""

    def test_embed_batch_single_text(self):
        """Single text returns one embedding vector."""
        mock_response = MagicMock()
        mock_item = MagicMock()
        mock_item.embedding = [0.1] * 1536
        mock_response.data = [mock_item]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("src.embeddings.openai_client._load_config") as mock_cfg:
                mock_cfg.return_value = {"openai_embeddings": {"model": "text-embedding-3-small", "dimensions": 1536, "batch_size": 100}}
                with patch("src.embeddings.openai_client.OpenAI") as MockOpenAI:
                    mock_client = MagicMock()
                    mock_client.embeddings.create.return_value = mock_response
                    MockOpenAI.return_value = mock_client

                    from src.embeddings.openai_client import EmbeddingClient
                    ec = EmbeddingClient()
                    result = ec.embed_batch(["hello world"])

                    assert len(result) == 1
                    assert result[0] == [0.1] * 1536
                    mock_client.embeddings.create.assert_called_once()

    def test_embed_batch_multiple_texts(self):
        """Multiple texts return corresponding embedding vectors."""
        mock_response = MagicMock()
        mock_item1 = MagicMock()
        mock_item1.embedding = [0.1] * 1536
        mock_item2 = MagicMock()
        mock_item2.embedding = [0.2] * 1536
        mock_response.data = [mock_item1, mock_item2]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("src.embeddings.openai_client._load_config") as mock_cfg:
                mock_cfg.return_value = {"openai_embeddings": {"model": "text-embedding-3-small", "dimensions": 1536, "batch_size": 100}}
                with patch("src.embeddings.openai_client.OpenAI") as MockOpenAI:
                    mock_client = MagicMock()
                    mock_client.embeddings.create.return_value = mock_response
                    MockOpenAI.return_value = mock_client

                    from src.embeddings.openai_client import EmbeddingClient
                    ec = EmbeddingClient()
                    result = ec.embed_batch(["hello", "world"])

                    assert len(result) == 2
                    mock_client.embeddings.create.assert_called_once()
                    call_args = mock_client.embeddings.create.call_args
                    assert call_args.kwargs["input"] == ["hello", "world"]

    def test_embed_batch_empty_list_returns_empty(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("src.embeddings.openai_client._load_config") as mock_cfg:
                mock_cfg.return_value = {"openai_embeddings": {"model": "text-embedding-3-small", "dimensions": 1536, "batch_size": 100}}
                with patch("src.embeddings.openai_client.OpenAI"):
                    from src.embeddings.openai_client import EmbeddingClient
                    ec = EmbeddingClient()
                    result = ec.embed_batch([])
                    assert result == []


class TestEmbedTextsAutoBatch:
    """Test auto-batching for large lists."""

    def test_embed_texts_respects_batch_size(self):
        """Long list is split into multiple API calls at batch_size."""
        mock_response = MagicMock()
        mock_item = MagicMock()
        mock_item.embedding = [0.1] * 1536
        mock_response.data = [mock_item]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("src.embeddings.openai_client._load_config") as mock_cfg:
                mock_cfg.return_value = {"openai_embeddings": {"model": "text-embedding-3-small", "dimensions": 1536, "batch_size": 2}}
                with patch("src.embeddings.openai_client.OpenAI") as MockOpenAI:
                    mock_client = MagicMock()
                    mock_client.embeddings.create.return_value = mock_response
                    MockOpenAI.return_value = mock_client

                    from src.embeddings.openai_client import EmbeddingClient
                    ec = EmbeddingClient()
                    # 5 texts, batch_size=2 → 3 API calls
                    texts = ["a", "b", "c", "d", "e"]
                    result = ec.embed_texts(texts)

                    assert mock_client.embeddings.create.call_count == 3


class TestEnvOnlyApiKey:
    """Test that API key comes from environment only."""

    def test_raises_if_no_api_key(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("src.embeddings.openai_client._load_config") as mock_cfg:
            mock_cfg.return_value = {"openai_embeddings": {"model": "text-embedding-3-small", "dimensions": 1536, "batch_size": 100}}
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                from src.embeddings.openai_client import EmbeddingClient
                EmbeddingClient()
