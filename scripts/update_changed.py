#!/usr/bin/env python3
"""Incrementally update the embedding index for changed files only.

Usage:
    python scripts/update_changed.py [--dry-run]

Compares file content hashes against the manifest and only re-indexes
files that have changed since the last full rebuild.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from embeddings.chunker import chunk_markdown
from embeddings.indexer import init_index, upsert_document, upsert_embedding, delete_documents_by_path
from embeddings.manifest import (
    compute_content_hash,
    load_manifest,
    write_manifest,
    touch_file_record,
    is_file_changed,
    remove_file_record,
    update_manifest_meta,
)
from embeddings.openai_client import get_client
from scripts.rebuild_index import discover_files  # noqa: F401


# Re-use discover_files from rebuild_index
def _get_discover_files():
    from scripts.rebuild_index import discover_files as _df, INDEXED_SUBDIRS, IGNORED_DIRS
    return _df


def main() -> None:
    parser = argparse.ArgumentParser(description="Incrementally update changed embeddings")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from gbrain.paths import get_gbrain_root

    gbrain_root = get_gbrain_root()
    manifest = load_manifest()

    if not args.dry_run:
        init_index()

    # Discover files
    from scripts.rebuild_index import discover_files
    files = discover_files(gbrain_root)

    changed: list[Path] = []
    removed: list[str] = []

    # Check for changed or new files
    for f in files:
        content = f.read_text(encoding="utf-8")
        content_hash = compute_content_hash(content)
        if is_file_changed(manifest, str(f), content_hash):
            changed.append(f)

    # Check for deleted files (in manifest but not on disk)
    indexed_files = set(manifest.get("files", {}).keys())
    disk_files = {str(f) for f in files}
    for old_path in indexed_files:
        if old_path not in disk_files:
            removed.append(old_path)

    print(f"Changed files : {len(changed)}")
    print(f"Removed files: {len(removed)}")

    if args.dry_run:
        for f in changed:
            print(f"  [dry-run] Would re-index : {Path(f).relative_to(gbrain_root)}")
        for p in removed:
            print(f"  [dry-run] Would remove   : {Path(p).relative_to(gbrain_root)}")
        print(f"\nDry run complete.")
        return

    client = get_client()

    # Remove embeddings for deleted files
    for old_path in removed:
        delete_documents_by_path(old_path)
        remove_file_record(manifest, old_path)
        print(f"  Removed: {old_path}")

    # Re-index changed files
    for f in changed:
        try:
            content = f.read_text(encoding="utf-8")
            content_hash = compute_content_hash(content)
            chunks = chunk_markdown(f)

            # Delete old chunks for this file
            delete_documents_by_path(str(f))

            # Re-add new chunks
            for chunk in chunks:
                doc_id = chunk["chunk_id"]
                upsert_document(
                    doc_id=doc_id,
                    path=str(f),
                    doc_type=_infer_doc_type(f),
                    title=chunk.get("title", ""),
                    content=chunk["content"],
                    content_hash=content_hash,
                )
                vector = client.embed_text(chunk["content"])
                upsert_embedding(
                    document_id=doc_id,
                    model=client.model,
                    dimensions=client.dimensions,
                    embedding=vector,
                )
                touch_file_record(manifest, str(f), content_hash, len(chunks))
            print(f"  Updated: {f.relative_to(gbrain_root)}")
        except Exception as e:
            print(f"  ERROR {f}: {e}", file=sys.stderr)

    update_manifest_meta(manifest, client.model, client.dimensions)
    write_manifest(manifest)
    print(f"\nDone.")


def _infer_doc_type(path: Path) -> str:
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


if __name__ == "__main__":
    main()
