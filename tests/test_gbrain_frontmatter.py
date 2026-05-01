"""Tests for gbrain/frontmatter.py"""

import pytest
from datetime import datetime

from src.gbrain.frontmatter import (
    parse_frontmatter,
    write_frontmatter,
    parse_date_from_frontmatter,
    extract_id_from_path,
)


class TestParseFrontmatter:
    def test_parses_valid_frontmatter(self) -> None:
        raw = '---\ntitle: Test\nstatus: active\n---\n\nBody content.'
        data, body = parse_frontmatter(raw)
        assert data["title"] == "Test"
        assert data["status"] == "active"
        assert body.strip() == "Body content."

    def test_no_frontmatter(self) -> None:
        raw = "Just plain text."
        data, body = parse_frontmatter(raw)
        assert data == {}
        assert body == raw

    def test_body_only_no_closing_delimiter(self) -> None:
        raw = "---\ntitle: No close\nBody"
        data, body = parse_frontmatter(raw)
        # gray-matter is lenient
        assert isinstance(data, dict)


class TestWriteFrontmatter:
    def test_roundtrips(self) -> None:
        data = {"title": "Roundtrip", "status": "active"}
        body = "Some content.\n\nMore content."
        out = write_frontmatter(data, body)
        parsed_data, parsed_body = parse_frontmatter(out)
        assert parsed_data["title"] == "Roundtrip"
        assert parsed_body.strip() == body

    def test_title_injected(self) -> None:
        data = {"status": "active"}
        out = write_frontmatter(data, "body", title="My Title")
        d, _ = parse_frontmatter(out)
        assert d.get("title") == "My Title"

    def test_date_injected(self) -> None:
        dt = datetime(2026, 5, 1, 12, 0, 0)
        out = write_frontmatter({}, "body", date=dt)
        d, _ = parse_frontmatter(out)
        assert "updated_at" in d


class TestParseDateFromFrontmatter:
    def test_iso_datetime(self) -> None:
        data = {"updated_at": "2026-05-01T20:00:00"}
        assert parse_date_from_frontmatter(data) == datetime(2026, 5, 1, 20, 0, 0)

    def test_date_only(self) -> None:
        data = {"date": "2026-05-01"}
        assert parse_date_from_frontmatter(data) == datetime(2026, 5, 1, 0, 0, 0)

    def test_missing(self) -> None:
        assert parse_date_from_frontmatter({}) is None


class TestExtractIdFromPath:
    def test_strips_md(self) -> None:
        assert extract_id_from_path("/path/to/my-file.md") == "my-file"

    def test_strips_status_prefix(self) -> None:
        assert extract_id_from_path("active_planning-loop.md") == "planning-loop"

    def test_plain_id(self) -> None:
        assert extract_id_from_path("decision_20260501_001.md") == "decision_20260501_001"
