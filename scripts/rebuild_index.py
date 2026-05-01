#!/usr/bin/env python3
"""Rebuild the full embedding index for all Reflex/GBrain files.

Usage:
    python scripts/rebuild_index.py [--dry-run]

This script:
1. Discovers all markdown files in allowed Reflex/GBrain directories
2. Chunks each file
3. Embeds each chunk with OpenAI text-embedding-3-small
4. Upserts chunks + embeddings into SQLite index
5. Updates the manifest
"""

import argparse
import sys
from pathlib import Path

# Ensure src/ is on path for script execution
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from embeddings.chunker import chunk_markdown
from embeddings.indexer import init_index, upsert_document, upsert_embedding
from embeddings.manifest import (
    compute_content_hash,
    load_manifest,
    write_manifest,
    touch_file_record,
    update_manifest_meta,
)
from embeddings.openai_client import get_client


# ---------------------------------------------------------------------------
# Allowed indexing paths (relative to GBrain root)
# ---------------------------------------------------------------------------

INDEXED_SUBDIRS = [
    "reflex/patterns",
    "reflex/experiments",
    "reflex/reviews",
    "reflex/checkins",
    "reflex/skillify-candidates",
    "reflex/contracts",
]

IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache"}


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def discover_files(gbrain_root: Path) -> list[Path]:
    """Find all .md files in indexed subdirs, excluding ignored directories."""
    files: list[Path] = []
    for subdir in INDEXED_SUBDIRS:
        dir_path = gbrain_root / subdir
        if not dir_path.exists():
            continue
        for f in dir_path.rglob("*.md"):
            # Skip if any parent dir is in ignored set
            if any(p.name in IGNORED_DIRS for p in f.parents):
                continue
            files.append(f)
    return sorted(files)


# ---------------------------------------------------------------------------
# Index a single file
# ---------------------------------------------------------------------------

def index_file(
    path: Path,
    client,
    manifest: dict,
) -> int:
    """Chunk and embed a single file. Returns number of chunks indexed."""
    content = path.read_text(encoding="utf-8")
    content_hash = compute_content_hash(content)
    chunks = chunk_markdown(path)

    doc_type = _infer_doc_type(path)

    for chunk in chunks:
        doc_id = chunk["chunk_id"]
        # Upsert document
        upsert_document(
            doc_id=doc_id,
            path=str(path),
            doc_type=doc_type,
            title=chunk.get("title", ""),
            content=chunk["content"],
            content_hash=content_hash,
        )
        # Embed and upsert
        vector = client.embed_text(chunk["content"])
        upsert_embedding(
            document_id=doc_id,
            model=client.model,
            dimensions=client.dimensions,
            embedding=vector,
        )

    # Update manifest
    touch_file_record(manifest, str(path), content_hash, len(chunks))
    return len(chunks)


def _infer_doc_type(path: Path) -> str:
    """Infer the document type from the path structure."""
    parts = path.parts
    if "patterns" in parts:
        return "pattern"
    elif "experiments" in parts:
        return "experiment"
    elif "reviews" in parts:
        return "review"
    elif "checkins" in parts:
        return "checkin"
    elif "contracts" in parts:
        return "contract"
    elif "signals" in parts:
        return "signal"
    elif "decisions" in parts:
        return "decision"
    elif "skillify-candidates" in parts:
        return "skillify"
    return "unknown"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the full Reflex embedding index")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be indexed without writing")
    args = parser.parse_args()

    import os
    from gbrain.paths import get_gbrain_root
    from gbrain.storage import ensure_reflex_structure

    gbrain_root = get_gbrain_root()
    print(f"GBrain root: {gbrain_root}")

    # Ensure structure exists
    if not args.dry_run:
        ensure_reflex_structure()

    # Ensure index is ready
    if not args.dry_run:
        init_index()

    # Discover files
    files = discover_files(gbrain_root)
    print(f"Found {len(files)} files to index")

    if args.dry_run:
        for f in files:
            print(f"  [dry-run] Would index: {f.relative_to(gbrain_root)}")
        print(f"\nDry run complete — {len(files)} files would be indexed.")
        return

    # Load manifest
    manifest = load_manifest()

    # Get embedding client
    client = get_client()
    update_manifest_meta(manifest, client.model, client.dimensions)

    total_chunks = 0
    for i, f in enumerate(files, 1):
        try:
            n = index_file(f, client, manifest)
            total_chunks += n
            print(f"[{i}/{len(files)}] {f.name} → {n} chunks")
        except Exception as e:
            print(f"[{i}/{len(files)}] ERROR {f.name}: {e}", file=sys.stderr)

    # Save manifest
    write_manifest(manifest)
    print(f"\nDone — indexed {total_chunks} chunks from {len(files)} files")
    print(f"Manifest written to: {manifest.get('_path', 'unknown')}")


if __name__ == "__main__":
    main()
