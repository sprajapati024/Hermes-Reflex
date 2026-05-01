"""SQLite vector index for Hermes Reflex embeddings.

Tables:
  - reflex_documents: id, path, type, title, content, summary, updated_at, content_hash
  - reflex_embeddings: document_id, model, dimensions, embedding_json, embedded_at

Uses JSON-stored float vectors with manual cosine similarity — appropriate for
small datasets (hundreds to low thousands of chunks). No sqlite-vec dependency.
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..gbrain.paths import get_embeddings_index_path


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reflex_documents (
    id          TEXT PRIMARY KEY,
    path        TEXT NOT NULL,
    type        TEXT NOT NULL,
    title       TEXT,
    content     TEXT NOT NULL,
    summary     TEXT,
    updated_at  TEXT NOT NULL,
    content_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reflex_embeddings (
    document_id  TEXT PRIMARY KEY,
    model        TEXT NOT NULL,
    dimensions   INTEGER NOT NULL,
    embedding_json TEXT NOT NULL,
    embedded_at  TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES reflex_documents(id)
);

CREATE INDEX IF NOT EXISTS idx_documents_path ON reflex_documents(path);
CREATE INDEX IF NOT EXISTS idx_documents_type ON reflex_documents(type);
"""

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS reflex_documents (
    id          TEXT PRIMARY KEY,
    path        TEXT NOT NULL,
    type        TEXT NOT NULL,
    title       TEXT,
    content     TEXT NOT NULL,
    summary     TEXT,
    updated_at  TEXT NOT NULL,
    content_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reflex_embeddings (
    document_id  TEXT PRIMARY KEY,
    model        TEXT NOT NULL,
    dimensions   INTEGER NOT NULL,
    embedding_json TEXT NOT NULL,
    embedded_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_path ON reflex_documents(path);
CREATE INDEX IF NOT EXISTS idx_documents_type ON reflex_documents(type);
"""


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def _get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = get_embeddings_index_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent read performance
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_index(db_path: Optional[Path] = None) -> None:
    """Create tables if they don't exist."""
    conn = _get_connection(db_path)
    try:
        conn.executescript(_INIT_SQL)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Document CRUD
# ---------------------------------------------------------------------------

def upsert_document(
    doc_id: str,
    path: str,
    doc_type: str,
    content: str,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    content_hash: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Insert or replace a document."""
    conn = _get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO reflex_documents (id, path, type, title, content, summary, updated_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                path=excluded.path,
                type=excluded.type,
                title=excluded.title,
                content=excluded.content,
                summary=excluded.summary,
                updated_at=excluded.updated_at,
                content_hash=excluded.content_hash
            """,
            (doc_id, path, doc_type, title, content, summary, datetime.now().isoformat(), content_hash),
        )
        conn.commit()
    finally:
        conn.close()


def delete_document(doc_id: str, db_path: Optional[Path] = None) -> None:
    """Delete a document and its embedding."""
    conn = _get_connection(db_path)
    try:
        conn.execute("DELETE FROM reflex_embeddings WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM reflex_documents WHERE id = ?", (doc_id,))
        conn.commit()
    finally:
        conn.close()


def delete_documents_by_path(path: str, db_path: Optional[Path] = None) -> None:
    """Delete all documents with a given path (e.g. when file is deleted)."""
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT id FROM reflex_documents WHERE path = ?", (path,)
        ).fetchall()
        for row in rows:
            conn.execute("DELETE FROM reflex_embeddings WHERE document_id = ?", (row["id"],))
        conn.execute("DELETE FROM reflex_documents WHERE path = ?", (path,))
        conn.commit()
    finally:
        conn.close()


def get_document(doc_id: str, db_path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    """Get a document by ID."""
    conn = _get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM reflex_documents WHERE id = ?", (doc_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_documents_by_type(doc_type: str, db_path: Optional[Path] = None) -> list[dict[str, Any]]:
    """Get all documents of a given type."""
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM reflex_documents WHERE type = ? ORDER BY updated_at DESC",
            (doc_type,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Embedding CRUD
# ---------------------------------------------------------------------------

def upsert_embedding(
    document_id: str,
    model: str,
    dimensions: int,
    embedding: list[float],
    db_path: Optional[Path] = None,
) -> None:
    """Insert or replace an embedding."""
    conn = _get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO reflex_embeddings (document_id, model, dimensions, embedding_json, embedded_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                model=excluded.model,
                dimensions=excluded.dimensions,
                embedding_json=excluded.embedding_json,
                embedded_at=excluded.embedded_at
            """,
            (document_id, model, dimensions, json.dumps(embedding), datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_embedding(document_id: str, db_path: Optional[Path] = None) -> Optional[list[float]]:
    """Get an embedding vector by document ID."""
    conn = _get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT embedding_json FROM reflex_embeddings WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        return json.loads(row["embedding_json"]) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def search_by_vector(
    query_vector: list[float],
    top_k: int = 8,
    doc_type: Optional[str] = None,
    min_score: float = 0.0,
    db_path: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Search for top_k most similar documents using cosine similarity.

    Args:
        query_vector: The query embedding vector.
        top_k: Maximum number of results to return.
        doc_type: Optional filter by document type.
        min_score: Minimum cosine similarity score (0.0–1.0).
        db_path: Optional path to the SQLite database.

    Returns:
        List of dicts with document fields plus a 'score' key.
    """
    conn = _get_connection(db_path)
    try:
        if doc_type:
            rows = conn.execute(
                """
                SELECT d.*, e.embedding_json
                FROM reflex_documents d
                JOIN reflex_embeddings e ON d.id = e.document_id
                WHERE d.type = ?
                """,
                (doc_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT d.*, e.embedding_json
                FROM reflex_documents d
                JOIN reflex_embeddings e ON d.id = e.document_id
                """,
            ).fetchall()

        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            vec = json.loads(row["embedding_json"])
            score = cosine_similarity(query_vector, vec)
            if score >= min_score:
                doc = dict(row)
                doc["score"] = round(score, 4)
                del doc["embedding_json"]  # Don't expose raw vector
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def get_stats(db_path: Optional[Path] = None) -> dict[str, int]:
    """Return document and embedding counts."""
    conn = _get_connection(db_path)
    try:
        doc_count = conn.execute("SELECT COUNT(*) FROM reflex_documents").fetchone()[0]
        emb_count = conn.execute("SELECT COUNT(*) FROM reflex_embeddings").fetchone()[0]
        return {"documents": doc_count, "embeddings": emb_count}
    finally:
        conn.close()
