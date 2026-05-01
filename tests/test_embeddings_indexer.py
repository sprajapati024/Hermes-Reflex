"""Tests for src/embeddings/indexer.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.embeddings.indexer import (
    cosine_similarity,
    delete_document,
    delete_documents_by_path,
    get_document,
    get_documents_by_type,
    get_embedding,
    get_stats,
    init_index,
    search_by_vector,
    upsert_document,
    upsert_embedding,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_index.sqlite"


@pytest.fixture(autouse=True)
def init(db_path):
    init_index(db_path)
    yield


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------

def test_cosine_similarity_identical_vectors():
    v = [0.1, 0.2, 0.3]
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0]
    assert cosine_similarity(v1, v2) == pytest.approx(0.0)


def test_cosine_similarity_opposite_vectors():
    v1 = [1.0, 0.0]
    v2 = [-1.0, 0.0]
    assert cosine_similarity(v1, v2) == pytest.approx(-1.0)


def test_cosine_similarity_length_mismatch_raises():
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])


def test_cosine_similarity_zero_vector():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


# ---------------------------------------------------------------------------
# upsert_document + get_document
# ---------------------------------------------------------------------------

def test_upsert_document_insert_and_retrieve(db_path):
    upsert_document(
        doc_id="doc1",
        path="/tmp/test.md",
        doc_type="pattern",
        title="Test Pattern",
        content="Pattern body content.",
        content_hash="abc123",
        db_path=db_path,
    )
    doc = get_document("doc1", db_path=db_path)
    assert doc is not None
    assert doc["id"] == "doc1"
    assert doc["title"] == "Test Pattern"
    assert doc["content"] == "Pattern body content."
    assert doc["type"] == "pattern"


def test_upsert_document_update(db_path):
    upsert_document(
        doc_id="doc1",
        path="/tmp/test.md",
        doc_type="pattern",
        title="Original",
        content="Original content",
        content_hash="v1",
        db_path=db_path,
    )
    upsert_document(
        doc_id="doc1",
        path="/tmp/test.md",
        doc_type="pattern",
        title="Updated",
        content="Updated content",
        content_hash="v2",
        db_path=db_path,
    )
    doc = get_document("doc1", db_path=db_path)
    assert doc["title"] == "Updated"
    assert doc["content"] == "Updated content"


def test_get_document_not_found(db_path):
    assert get_document("nonexistent", db_path=db_path) is None


# ---------------------------------------------------------------------------
# upsert_embedding + get_embedding
# ---------------------------------------------------------------------------

def test_upsert_and_get_embedding(db_path):
    vector = [0.1] * 1536
    upsert_embedding("doc1", "text-embedding-3-small", 1536, vector, db_path=db_path)
    retrieved = get_embedding("doc1", db_path=db_path)
    assert retrieved == vector


def test_get_embedding_not_found(db_path):
    assert get_embedding("nonexistent", db_path=db_path) is None


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------

def test_delete_document(db_path):
    upsert_document("doc2", "/tmp/test2.md", "experiment", "content", content_hash="x", db_path=db_path)
    upsert_embedding("doc2", "model", 1536, [0.1] * 1536, db_path=db_path)
    delete_document("doc2", db_path=db_path)
    assert get_document("doc2", db_path=db_path) is None
    assert get_embedding("doc2", db_path=db_path) is None


# ---------------------------------------------------------------------------
# delete_documents_by_path
# ---------------------------------------------------------------------------

def test_delete_documents_by_path(db_path):
    upsert_document("doc3", "/tmp/test3.md", "pattern", "content A", content_hash="x", db_path=db_path)
    upsert_embedding("doc3", "model", 1536, [0.1] * 1536, db_path=db_path)
    upsert_document("doc4", "/tmp/test3.md", "pattern", "content B", content_hash="y", db_path=db_path)
    upsert_embedding("doc4", "model", 1536, [0.2] * 1536, db_path=db_path)
    delete_documents_by_path("/tmp/test3.md", db_path=db_path)
    assert get_document("doc3", db_path=db_path) is None
    assert get_document("doc4", db_path=db_path) is None


# ---------------------------------------------------------------------------
# get_documents_by_type
# ---------------------------------------------------------------------------

def test_get_documents_by_type(db_path):
    upsert_document("p1", "/tmp/p1.md", "pattern", "Pattern 1", "c", content_hash="x", db_path=db_path)
    upsert_document("p2", "/tmp/p2.md", "pattern", "Pattern 2", "c", content_hash="y", db_path=db_path)
    upsert_document("e1", "/tmp/e1.md", "experiment", "Exp 1", "c", content_hash="z", db_path=db_path)
    docs = get_documents_by_type("pattern", db_path=db_path)
    assert len(docs) == 2
    assert all(d["type"] == "pattern" for d in docs)


# ---------------------------------------------------------------------------
# search_by_vector
# ---------------------------------------------------------------------------

def test_search_by_vector_returns_best_match(db_path):
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [0.0, 1.0, 0.0]

    upsert_document("d1", "/tmp/d1.md", "pattern", "Doc 1", "content", content_hash="x", db_path=db_path)
    upsert_embedding("d1", "test", 3, vec1, db_path=db_path)
    upsert_document("d2", "/tmp/d2.md", "pattern", "Doc 2", "content", content_hash="y", db_path=db_path)
    upsert_embedding("d2", "test", 3, vec2, db_path=db_path)

    results = search_by_vector([0.99, 0.0, 0.0], top_k=2, db_path=db_path)
    assert len(results) == 2
    assert results[0]["id"] == "d1"
    assert results[0]["score"] == pytest.approx(1.0)


def test_search_by_vector_min_score_filter(db_path):
    vec1 = [1.0, 0.0]
    vec2 = [0.0, 1.0]
    upsert_document("s1", "/tmp/s1.md", "pattern", "S1", "c", content_hash="x", db_path=db_path)
    upsert_embedding("s1", "test", 2, vec1, db_path=db_path)
    upsert_document("s2", "/tmp/s2.md", "pattern", "S2", "c", content_hash="y", db_path=db_path)
    upsert_embedding("s2", "test", 2, vec2, db_path=db_path)

    results = search_by_vector([0.5, 0.5], top_k=2, min_score=0.8, db_path=db_path)
    # Both are at cosim 0.707 — above 0.8? No. So filter returns nothing at very high threshold
    assert all(r["score"] >= 0.8 for r in results)


def test_search_by_vector_doc_type_filter(db_path):
    vec = [0.7, 0.7]
    upsert_document("t1", "/tmp/t1.md", "pattern", "P", "c", content_hash="x", db_path=db_path)
    upsert_embedding("t1", "test", 2, vec, db_path=db_path)
    upsert_document("t2", "/tmp/t2.md", "experiment", "E", "c", content_hash="y", db_path=db_path)
    upsert_embedding("t2", "test", 2, vec, db_path=db_path)

    results = search_by_vector(vec, top_k=5, doc_type="pattern", db_path=db_path)
    assert all(r["type"] == "pattern" for r in results)


def test_search_by_vector_top_k(db_path):
    for i in range(10):
        vec = [float(i) * 0.1, 0.5]
        upsert_document(f"k{i}", f"/tmp/k{i}.md", "pattern", f"K{i}", "c", content_hash=str(i), db_path=db_path)
        upsert_embedding(f"k{i}", "test", 2, vec, db_path=db_path)

    results = search_by_vector([0.9, 0.5], top_k=3, db_path=db_path)
    assert len(results) == 3


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

def test_get_stats(db_path):
    upsert_document("st1", "/tmp/st1.md", "pattern", "S1", "c", content_hash="x", db_path=db_path)
    upsert_embedding("st1", "test", 2, [0.1, 0.2], db_path=db_path)
    upsert_document("st2", "/tmp/st2.md", "pattern", "S2", "c", content_hash="y", db_path=db_path)
    upsert_embedding("st2", "test", 2, [0.3, 0.4], db_path=db_path)
    stats = get_stats(db_path=db_path)
    assert stats["documents"] == 2
    assert stats["embeddings"] == 2
