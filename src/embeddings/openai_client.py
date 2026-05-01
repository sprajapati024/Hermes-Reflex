"""OpenAI embedding client for Hermes Reflex.

API key is loaded from environment only — never hardcoded.
Configured via config.yaml (model, dimensions, batch_size).
"""

from __future__ import annotations

import os
from typing import Optional

import yaml
from openai import OpenAI  # noqa: F401 — imported here so it can be patched in tests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    """Load embedding config from config.yaml."""
    from ..core.config import load_config
    return load_config()


def get_embedding_config() -> dict:
    cfg = _load_config()
    return {
        "model": cfg.get("openai_embeddings", {}).get("model", "text-embedding-3-small"),
        "dimensions": cfg.get("openai_embeddings", {}).get("dimensions", 1536),
        "batch_size": cfg.get("openai_embeddings", {}).get("batch_size", 100),
    }


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class EmbeddingClient:
    """OpenAI embedding client with env-only API key."""

    def __init__(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        self._client = OpenAI(api_key=api_key)
        self._config = get_embedding_config()

    @property
    def model(self) -> str:
        return self._config["model"]

    @property
    def dimensions(self) -> int:
        return self._config["dimensions"]

    @property
    def batch_size(self) -> int:
        return self._config["batch_size"]

    def embed_text(self, text: str) -> list[float]:
        """Embed a single string. Returns a list of floats."""
        response = self._client.embeddings.create(
            model=self.model,
            input=[text],
            encoding_format="float",
            dimensions=self.dimensions,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple strings in one batch API call."""
        if not texts:
            return []
        response = self._client.embeddings.create(
            model=self.model,
            input=texts,
            encoding_format="float",
            dimensions=self.dimensions,
        )
        # Response.data is ordered the same as input
        return [item.embedding for item in response.data]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of strings, auto-batching at configured batch_size.

        Chunks the input list and makes sequential API calls if needed.
        Returns embeddings in the same order as input.
        """
        if not texts:
            return []

        results: list[list[float]] = []
        batch_size = self.batch_size

        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            results.extend(self.embed_batch(chunk))

        return results


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_Client: Optional[EmbeddingClient] = None


def get_client() -> EmbeddingClient:
    """Return a singleton EmbeddingClient instance."""
    global _Client
    if _Client is None:
        _Client = EmbeddingClient()
    return _Client


def embed_text(text: str) -> list[float]:
    """Embed a single string using the global client."""
    return get_client().embed_text(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed multiple strings using the global client with auto-batching."""
    return get_client().embed_texts(texts)
