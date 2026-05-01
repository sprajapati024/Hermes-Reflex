"""Markdown chunker for Hermes Reflex.

Splits markdown files into semantically coherent chunks suitable for embedding.
- Frontmatter is stripped (metadata not part of content embedding)
- Chunks are bounded by H2/H3 section headings when possible
- Overlap across sections to preserve context
- Each chunk is a dict with: chunk_id, path, title, content, source_type
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import frontmatter

# ---------------------------------------------------------------------------
# Chunking constants
# ---------------------------------------------------------------------------

MAX_CHUNK_WORDS = 300
MIN_CHUNK_WORDS = 50
SECTION_OVERLAP_LINES = 5


# ---------------------------------------------------------------------------
# Core chunking
# ---------------------------------------------------------------------------

def _compute_chunk_id(path: Path, text: str, index: int) -> str:
    """Generate a deterministic chunk ID from path + content hash + index."""
    unique = f"{path}:{text}:{index}".encode()
    return hashlib.sha256(unique).hexdigest()[:16]


def _strip_frontmatter(raw: str) -> tuple[str, dict[str, Any]]:
    """Strip YAML frontmatter from raw markdown. Returns (body, metadata)."""
    try:
        post = frontmatter.loads(raw)
        return post.content, dict(post)
    except Exception:
        return raw, {}


def _split_by_heading(content: str) -> list[tuple[str, str]]:
    """Split markdown content by H2 (##) and H3 (###) headings.

    Returns a list of (heading_title, section_content) tuples.
    The first section may have no heading (introduction).
    """
    lines = content.splitlines()
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    heading_re = re.compile(r"^(#{2,3})\s+(.+)$")

    for line in lines:
        m = heading_re.match(line)
        if m:
            # Save previous section
            if current_lines or sections:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = m.group(2).strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    # Final section
    if current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))

    return sections


def _count_words(text: str) -> int:
    return len(text.split())


def _chunk_section(
    heading: str,
    content: str,
    path: Path,
    start_index: int,
) -> list[dict[str, Any]]:
    """Break a section into word-bounded chunks with overlap."""
    words = content.split()
    chunks: list[dict[str, Any]] = []

    if not words:
        return chunks

    if _count_words(content) <= MAX_CHUNK_WORDS:
        chunk_id = _compute_chunk_id(path, content, start_index)
        chunks.append({
            "chunk_id": chunk_id,
            "path": str(path),
            "title": heading or path.stem,
            "content": content.strip(),
            "source_type": "section",
        })
        return chunks

    # Sliding window by words
    start = 0
    index = start_index
    while start < len(words):
        end = start + MAX_CHUNK_WORDS
        window = words[start:end]
        chunk_text = " ".join(window)

        if _count_words(chunk_text) < MIN_CHUNK_WORDS and len(chunks) > 0:
            # Merge with previous chunk if too small
            chunks[-1]["content"] += " " + chunk_text
            chunks[-1]["content"] = chunks[-1]["content"].strip()
            break

        chunk_id = _compute_chunk_id(path, chunk_text, index)
        chunks.append({
            "chunk_id": chunk_id,
            "path": str(path),
            "title": heading or path.stem,
            "content": chunk_text.strip(),
            "source_type": "section",
        })

        # Move window forward with overlap
        step = MAX_CHUNK_WORDS - SECTION_OVERLAP_LINES
        start = max(start + step, start + 1)
        index += 1

    return chunks


def chunk_markdown(path: Path) -> list[dict[str, Any]]:
    """Chunk a markdown file into semantically coherent pieces.

    Args:
        path: Path to a .md file.

    Returns:
        List of chunk dicts with keys: chunk_id, path, title, content, source_type.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise IOError(f"Failed to read {path}: {e}")

    body, metadata = _strip_frontmatter(raw)
    sections = _split_by_heading(body)

    all_chunks: list[dict[str, Any]] = []
    global_index = 0

    for heading, section_content in sections:
        if not section_content.strip():
            continue
        chunks = _chunk_section(heading, section_content, path, global_index)
        all_chunks.extend(chunks)
        global_index += len(chunks)

    # If no sections split (no headings), chunk the whole body as one
    if not all_chunks:
        content = body.strip()
        if content:
            chunk_id = _compute_chunk_id(path, content, 0)
            all_chunks.append({
                "chunk_id": chunk_id,
                "path": str(path),
                "title": metadata.get("title", path.stem),
                "content": content,
                "source_type": "full",
            })

    # Attach metadata as chunk fields
    for chunk in all_chunks:
        chunk["metadata"] = metadata

    return all_chunks


def chunk_text(text: str, source_path: str = "unknown") -> list[dict[str, Any]]:
    """Chunk plain text (no frontmatter) into pieces.

    Used for inline content that isn't a file (e.g. user message chunks).
    """
    words = text.split()
    chunks: list[dict[str, Any]] = []

    for i in range(0, len(words), MAX_CHUNK_WORDS):
        window = words[i:i + MAX_CHUNK_WORDS]
        chunk_text = " ".join(window)
        chunk_id = _compute_chunk_id(Path(source_path), chunk_text, i)
        chunks.append({
            "chunk_id": chunk_id,
            "path": source_path,
            "title": "",
            "content": chunk_text.strip(),
            "source_type": "text",
        })

    return chunks
