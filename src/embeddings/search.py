"""Semantic search / retrieval for Hermes Reflex.

search_reflex_memory() is the main entry point. It:
1. Embeds the query using OpenAI
2. Searches the SQLite index by cosine similarity
3. Falls back to keyword search if vector search returns nothing
4. Returns top_k results with path, type, score, title, summary, content snippet
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

from .chunker import chunk_markdown
from .indexer import cosine_similarity, search_by_vector, get_documents_by_type
from .manifest import compute_content_hash, file_needs_indexing, is_file_changed, load_manifest
from .openai_client import get_client


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TOP_K = 8
DEFAULT_MIN_SCORE = 0.65

# Allowed paths for retrieval (from config.yaml reflex.retrieval.allowed_paths)
ALLOWED_GLOBS = [
    "reflex/patterns/**",
    "reflex/experiments/**",
    "reflex/reviews/**",
    "reflex/checkins/**",
    "reflex/skillify-candidates/**",
    "reflex/contracts/**",
    "projects/active/**",
]


# ---------------------------------------------------------------------------
# Index bootstrap
# ---------------------------------------------------------------------------

def ensure_index_ready() -> None:
    """Ensure the index DB and manifest exist."""
    from .indexer import init_index
    from ..gbrain.paths import ensure_dir
    manifest_path = get_manifest_path()
    if manifest_path.parent:
        ensure_dir(manifest_path.parent)
    init_index()


def get_manifest_path() -> Path:
    from ..gbrain.paths import get_embeddings_manifest_path
    return get_embeddings_manifest_path()


# ---------------------------------------------------------------------------
# Core retrieval
# ---------------------------------------------------------------------------

def search_reflex_memory(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_MIN_SCORE,
    doc_types: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Search indexed Reflex/GBrain memory for relevant evidence.

    Args:
        query: Natural language query string.
        top_k: Maximum number of results to return.
        min_score: Minimum cosine similarity score (0.0–1.0).
        doc_types: Optional list of document types to filter (e.g. ["pattern", "experiment"]).

    Returns:
        List of result dicts sorted by relevance score descending.
        Each dict has: chunk_id, path, type, title, content, summary, score.
    """
    # 1. Embed query
    client = get_client()
    query_vector = client.embed_text(query)

    # 2. Try vector search
    results: list[dict[str, Any]] = []
    for doc_type in (doc_types or [None]):
        hits = search_by_vector(
            query_vector=query_vector,
            top_k=top_k,
            min_score=min_score,
            doc_type=doc_type,
        )
        results.extend(hits)

    # Deduplicate by doc_id, re-sort
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for r in sorted(results, key=lambda x: x["score"], reverse=True):
        if r["id"] not in seen:
            seen.add(r["id"])
            deduped.append(r)

    # 3. Fallback to keyword search if no vector hits
    if not deduped:
        deduped = _keyword_fallback(query, top_k)

    return deduped[:top_k]


# ---------------------------------------------------------------------------
# Keyword fallback
# ---------------------------------------------------------------------------

def _normalize_for_search(text: str) -> str:
    """Lowercase, strip extra whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _keyword_fallback(
    query: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """Simple keyword search across all documents when vector search yields nothing.

    Matches query words against path, title, and content.
    """
    query_words = _normalize_for_search(query).split()
    if not query_words:
        return []

    from ..gbrain.paths import get_reflex_root, get_gbrain_root

    candidates: list[tuple[int, dict[str, Any]]] = []

    # Search across all documents in the index
    all_docs = _get_all_indexed_docs()

    for doc in all_docs:
        score = 0
        searchable = _normalize_for_search(
            f"{doc.get('title', '')} {doc.get('content', '')} {doc.get('path', '')}"
        )
        matched = sum(1 for w in query_words if w in searchable)
        if matched > 0:
            # Score = fraction of query words matched × boost by match count
            score = (matched / len(query_words)) * (1.0 + 0.1 * matched)
            candidates.append((score, doc))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [dict(doc) for _, doc in candidates[:top_k]]


def _get_all_indexed_docs() -> list[dict[str, Any]]:
    """Load all documents from the index."""
    from .indexer import get_documents_by_type
    all_docs: list[dict[str, Any]] = []
    for doc_type in ["pattern", "experiment", "review", "checkin", "contract", "signal", "decision"]:
        all_docs.extend(get_documents_by_type(doc_type))
    return all_docs


# ---------------------------------------------------------------------------
# Single-doc retrieval (for context injection)
# ---------------------------------------------------------------------------

def retrieve_for_context(
    query: str,
    allowed_types: Optional[list[str]] = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Retrieve a small number of highly relevant chunks for context injection.

    Used by the critic/middleware to pull evidence before making a decision.
    """
    return search_reflex_memory(query, top_k=top_k, min_score=0.5, doc_types=allowed_types)
