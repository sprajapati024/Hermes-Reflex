"""Manifest tracker for Hermes Reflex embedding index.

The manifest tracks which files have been indexed and their content hashes.
This enables efficient incremental updates — only re-index files whose content changed.

Manifest file: gbrain/reflex/embeddings/manifest.json

Schema:
{
  "version": 1,
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "indexed_at": "ISO timestamp",
  "files": {
    "/absolute/path/to/file.md": {
      "hash": "sha256 of content",
      "chunk_count": 5,
      "indexed_at": "ISO timestamp"
    }
  }
}
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional

from ..gbrain.paths import get_embeddings_manifest_path


# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

MANIFEST_VERSION = 1


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hex digest of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hex digest of a file's content."""
    return compute_content_hash(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Manifest load/dump
# ---------------------------------------------------------------------------

def _default_manifest() -> dict[str, Any]:
    return {
        "version": MANIFEST_VERSION,
        "model": "",
        "dimensions": 0,
        "indexed_at": "",
        "files": {},
    }


def load_manifest(path: Optional[Path] = None) -> dict[str, Any]:
    """Load the manifest from disk, or return a clean default if missing."""
    if path is None:
        path = get_embeddings_manifest_path()
    if not path.exists():
        return _default_manifest()
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_manifest(manifest: dict[str, Any], path: Optional[Path] = None) -> None:
    """Write the manifest to disk, creating parent dirs if needed."""
    if path is None:
        path = get_embeddings_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Manifest operations
# ---------------------------------------------------------------------------

def touch_file_record(
    manifest: dict[str, Any],
    file_path: str,
    content_hash: str,
    chunk_count: int,
) -> None:
    """Update or add a file record in the manifest."""
    manifest["files"][file_path] = {
        "hash": content_hash,
        "chunk_count": chunk_count,
        "indexed_at": manifest.get("indexed_at", ""),
    }


def is_file_changed(
    manifest: dict[str, Any],
    file_path: str,
    current_hash: str,
) -> bool:
    """Return True if the file's hash differs from the manifest record."""
    record = manifest.get("files", {}).get(file_path)
    if record is None:
        return True
    return record.get("hash") != current_hash


def remove_file_record(manifest: dict[str, Any], file_path: str) -> None:
    """Remove a file record from the manifest."""
    manifest.get("files", {}).pop(file_path, None)


def get_indexed_files(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the files dict from the manifest."""
    return manifest.get("files", {})


def update_manifest_meta(
    manifest: dict[str, Any],
    model: str,
    dimensions: int,
) -> None:
    """Update manifest metadata."""
    from datetime import datetime
    manifest["version"] = MANIFEST_VERSION
    manifest["model"] = model
    manifest["dimensions"] = dimensions
    manifest["indexed_at"] = datetime.now().isoformat()


# ---------------------------------------------------------------------------
# Convenience: check + update
# ---------------------------------------------------------------------------

def file_needs_indexing(
    file_path: Path,
    manifest: Optional[dict[str, Any]] = None,
) -> tuple[bool, str]:
    """Check if a file needs indexing.

    Returns (needs_indexing, current_hash).
    """
    if manifest is None:
        manifest = load_manifest()
    current_hash = compute_file_hash(file_path)
    changed = is_file_changed(manifest, str(file_path), current_hash)
    return changed, current_hash
