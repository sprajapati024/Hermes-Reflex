"""Hermes Reflex — Embeddings package.

Modules:
    openai_client: OpenAI embedding client (env-only API key)
    chunker: Markdown chunking (frontmatter-aware, section-split)
    indexer: SQLite vector index with cosine similarity
    manifest: Hash-based change tracking for incremental rebuilds
    search: Semantic retrieval with keyword fallback
"""

from __future__ import annotations

from . import chunker
from . import indexer
from . import manifest
from . import openai_client
from . import search

__all__ = [
    "chunker",
    "indexer",
    "manifest",
    "openai_client",
    "search",
]
