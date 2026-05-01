"""Tests for src/embeddings/chunker.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.embeddings.chunker import (
    MAX_CHUNK_WORDS,
    MIN_CHUNK_WORDS,
    _strip_frontmatter,
    _split_by_heading,
    _count_words,
    chunk_markdown,
    chunk_text,
)


# ---------------------------------------------------------------------------
# _strip_frontmatter
# ---------------------------------------------------------------------------

def test_strip_frontmatter_parses_yaml():
    raw = "---\ntitle: Test\nstatus: active\n---\n\nBody content here."
    body, meta = _strip_frontmatter(raw)
    assert body.strip() == "Body content here."
    assert meta["title"] == "Test"
    assert meta["status"] == "active"


def test_strip_frontmatter_no_frontmatter():
    raw = "# Just a heading\n\nSome content."
    body, meta = _strip_frontmatter(raw)
    assert "Just a heading" in body
    assert meta == {}


def test_strip_frontmatter_invalid_yaml_falls_back():
    raw = "---\ntitle: broken: yaml::\n---\nBody."
    body, meta = _strip_frontmatter(raw)
    assert "Body" in body


# ---------------------------------------------------------------------------
# _split_by_heading
# ---------------------------------------------------------------------------

def test_split_by_heading_two_sections():
    content = "Intro text.\n\n## Section One\nSection one content.\n\n## Section Two\nSection two content."
    sections = _split_by_heading(content)
    assert len(sections) == 3  # intro + two sections
    headings = [h for h, _ in sections]
    assert "Section One" in headings
    assert "Section Two" in headings


def test_split_by_heading_no_headings():
    content = "Just a paragraph with no headings."
    sections = _split_by_heading(content)
    assert len(sections) == 1
    assert sections[0][0] == ""  # no heading


def test_split_by_heading_h3_supported():
    content = "## H2 Section\nContent\n\n### H3 Subsection\nSub content"
    sections = _split_by_heading(content)
    headings = [h for h, _ in sections]
    assert "H2 Section" in headings
    assert "H3 Subsection" in headings


# ---------------------------------------------------------------------------
# _count_words
# ---------------------------------------------------------------------------

def test_count_words():
    assert _count_words("hello world") == 2
    assert _count_words("") == 0
    # split() strips whitespace so leading/trailing spaces don't create extra words
    assert _count_words("  spaced   out  ") == 2


# ---------------------------------------------------------------------------
# chunk_markdown
# ---------------------------------------------------------------------------

def test_chunk_markdown_no_headings_short_file(tmp_path):
    """A short file with no headings returns one chunk."""
    f = tmp_path / "test.md"
    f.write_text("This is a short note.")
    chunks = chunk_markdown(f)
    assert len(chunks) == 1
    assert chunks[0]["content"] == "This is a short note."
    # Short file has no headings so it becomes a single "section" chunk
    assert chunks[0]["source_type"] == "section"


def test_chunk_markdown_strips_frontmatter(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\ntitle: My Note\n---\n\nFrontmatter should be stripped.")
    chunks = chunk_markdown(f)
    assert len(chunks) >= 1
    # Frontmatter content should not appear in chunk content
    for chunk in chunks:
        assert "title: My Note" not in chunk["content"]


def test_chunk_markdown_section_headings_become_chunks(tmp_path):
    f = tmp_path / "test.md"
    f.write_text(
        "## Heading One\nLong " * 100 + "\n\n## Heading Two\nLong " * 100
    )
    chunks = chunk_markdown(f)
    titles = [c["title"] for c in chunks]
    assert "Heading One" in titles
    assert "Heading Two" in titles


def test_chunk_markdown_respects_max_words(tmp_path):
    f = tmp_path / "test.md"
    # Write a section with 500 words (well over MAX_CHUNK_WORDS)
    content = "## Section\n" + ("word " * 500)
    f.write_text(content)
    chunks = chunk_markdown(f)
    for chunk in chunks:
        assert _count_words(chunk["content"]) <= MAX_CHUNK_WORDS + 10  # small buffer


def test_chunk_markdown_returns_valid_chunk_dict(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("# Title\n\nSome content here.")
    chunks = chunk_markdown(f)
    assert len(chunks) > 0
    chunk = chunks[0]
    assert "chunk_id" in chunk
    assert "path" in chunk
    assert "title" in chunk
    assert "content" in chunk
    assert "source_type" in chunk
    # chunk_id should be a 16-char hex string
    assert len(chunk["chunk_id"]) == 16


def test_chunk_markdown_nonexistent_file_raises(tmp_path):
    f = tmp_path / "nonexistent.md"
    with pytest.raises(IOError):
        chunk_markdown(f)


def test_chunk_markdown_preserves_path_in_chunk(tmp_path):
    f = tmp_path / "my_pattern.md"
    f.write_text("Pattern content.")
    chunks = chunk_markdown(f)
    assert chunks[0]["path"] == str(f)


# ---------------------------------------------------------------------------
# chunk_text (plain text, no file)
# ---------------------------------------------------------------------------

def test_chunk_text_short():
    chunks = chunk_text("short text")
    assert len(chunks) == 1
    assert chunks[0]["content"] == "short text"
    assert chunks[0]["source_type"] == "text"


def test_chunk_text_long_splits():
    words = " ".join([f"word{i}" for i in range(600)])
    chunks = chunk_text(words)
    assert len(chunks) > 1
    for chunk in chunks:
        assert _count_words(chunk["content"]) <= MAX_CHUNK_WORDS


def test_chunk_text_returns_unique_ids():
    chunks = chunk_text("word " * 600)
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids))  # all unique
