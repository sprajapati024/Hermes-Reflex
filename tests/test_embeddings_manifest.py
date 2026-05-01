"""Tests for src/embeddings/manifest.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.embeddings.manifest import (
    MANIFEST_VERSION,
    compute_content_hash,
    compute_file_hash,
    file_needs_indexing,
    get_indexed_files,
    is_file_changed,
    load_manifest,
    remove_file_record,
    touch_file_record,
    update_manifest_meta,
    write_manifest,
)


# ---------------------------------------------------------------------------
# compute_content_hash
# ---------------------------------------------------------------------------

def test_compute_content_hash_deterministic():
    h1 = compute_content_hash("hello world")
    h2 = compute_content_hash("hello world")
    assert h1 == h2


def test_compute_content_hash_different_inputs():
    h1 = compute_content_hash("hello")
    h2 = compute_content_hash("world")
    assert h1 != h2


# ---------------------------------------------------------------------------
# load_manifest + write_manifest
# ---------------------------------------------------------------------------

def test_write_and_load_manifest(tmp_path):
    manifest = {
        "version": 1,
        "model": "text-embedding-3-small",
        "dimensions": 1536,
        "indexed_at": "2025-01-01T00:00:00",
        "files": {},
    }
    path = tmp_path / "manifest.json"
    write_manifest(manifest, path)
    loaded = load_manifest(path)
    assert loaded["version"] == 1
    assert loaded["model"] == "text-embedding-3-small"


def test_load_manifest_missing_returns_default(tmp_path):
    missing = tmp_path / "nonexistent.json"
    manifest = load_manifest(missing)
    assert manifest["version"] == MANIFEST_VERSION
    assert manifest["files"] == {}


# ---------------------------------------------------------------------------
# touch_file_record
# ---------------------------------------------------------------------------

def test_touch_file_record_adds_entry():
    manifest = {"files": {}}
    touch_file_record(manifest, "/tmp/test.md", "abc123", 5)
    assert "/tmp/test.md" in manifest["files"]
    assert manifest["files"]["/tmp/test.md"]["hash"] == "abc123"
    assert manifest["files"]["/tmp/test.md"]["chunk_count"] == 5


def test_touch_file_record_updates_existing():
    manifest = {
        "files": {
            "/tmp/test.md": {"hash": "old", "chunk_count": 1, "indexed_at": "2025-01-01"}
        }
    }
    touch_file_record(manifest, "/tmp/test.md", "new", 3)
    assert manifest["files"]["/tmp/test.md"]["hash"] == "new"
    assert manifest["files"]["/tmp/test.md"]["chunk_count"] == 3


# ---------------------------------------------------------------------------
# is_file_changed
# ---------------------------------------------------------------------------

def test_is_file_changed_new_file():
    manifest = {"files": {}}
    assert is_file_changed(manifest, "/tmp/test.md", "abc123") is True


def test_is_file_changed_same_hash():
    manifest = {"files": {"/tmp/test.md": {"hash": "abc123", "chunk_count": 1, "indexed_at": ""}}}
    assert is_file_changed(manifest, "/tmp/test.md", "abc123") is False


def test_is_file_changed_different_hash():
    manifest = {"files": {"/tmp/test.md": {"hash": "abc123", "chunk_count": 1, "indexed_at": ""}}}
    assert is_file_changed(manifest, "/tmp/test.md", "xyz789") is True


# ---------------------------------------------------------------------------
# remove_file_record
# ---------------------------------------------------------------------------

def test_remove_file_record():
    manifest = {
        "files": {
            "/tmp/a.md": {"hash": "a", "chunk_count": 1, "indexed_at": ""},
            "/tmp/b.md": {"hash": "b", "chunk_count": 2, "indexed_at": ""},
        }
    }
    remove_file_record(manifest, "/tmp/a.md")
    assert "/tmp/a.md" not in manifest["files"]
    assert "/tmp/b.md" in manifest["files"]


# ---------------------------------------------------------------------------
# get_indexed_files
# ---------------------------------------------------------------------------

def test_get_indexed_files():
    manifest = {
        "files": {
            "/tmp/a.md": {"hash": "a", "chunk_count": 1, "indexed_at": ""},
        }
    }
    files = get_indexed_files(manifest)
    assert "/tmp/a.md" in files


# ---------------------------------------------------------------------------
# update_manifest_meta
# ---------------------------------------------------------------------------

def test_update_manifest_meta():
    manifest = {}
    update_manifest_meta(manifest, "text-embedding-3-small", 1536)
    assert manifest["version"] == MANIFEST_VERSION
    assert manifest["model"] == "text-embedding-3-small"
    assert manifest["dimensions"] == 1536
    assert manifest["indexed_at"] != ""


# ---------------------------------------------------------------------------
# file_needs_indexing
# ---------------------------------------------------------------------------

def test_file_needs_indexing_new_file(tmp_path):
    f = tmp_path / "new.md"
    f.write_text("content here")
    manifest = {"files": {}}
    needs, hash_val = file_needs_indexing(f, manifest)
    assert needs is True


def test_file_needs_indexing_unchanged_file(tmp_path):
    f = tmp_path / "same.md"
    f.write_text("same content")
    content_hash = compute_content_hash("same content")
    manifest = {
        "files": {
            str(f): {"hash": content_hash, "chunk_count": 1, "indexed_at": ""}
        }
    }
    needs, _ = file_needs_indexing(f, manifest)
    assert needs is False


def test_file_needs_indexing_changed_file(tmp_path):
    f = tmp_path / "changed.md"
    f.write_text("new content")
    manifest = {
        "files": {
            str(f): {"hash": "oldhash", "chunk_count": 1, "indexed_at": ""}
        }
    }
    needs, _ = file_needs_indexing(f, manifest)
    assert needs is True


# ---------------------------------------------------------------------------
# compute_file_hash
# ---------------------------------------------------------------------------

def test_compute_file_hash(tmp_path):
    f = tmp_path / "filehash.md"
    f.write_text("file content")
    h = compute_file_hash(f)
    assert h == compute_content_hash("file content")
