"""Markdown file reader and writer for GBrain/Reflex storage."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .frontmatter import parse_frontmatter, write_frontmatter, parse_date_from_frontmatter
from .paths import ensure_dir


def read_markdown(path: Path) -> tuple[dict[str, Any], str]:
    """Read a markdown file and return (frontmatter, body)."""
    raw = path.read_text(encoding="utf-8")
    return parse_frontmatter(raw)


def write_markdown(
    path: Path,
    body: str,
    data: Optional[dict[str, Any]] = None,
    *,
    title: Optional[str] = None,
    date: Optional[datetime] = None,
    auto_date: bool = True,
) -> Path:
    """Write a markdown file with frontmatter.

    Args:
        path: Destination file path. Parent dirs are created automatically.
        body: Markdown body content.
        data: Frontmatter dict to serialise.
        title: Optional title field.
        date: Optional date field. Defaults to now() if auto_date=True.
    """
    if data is None:
        data = {}
    if auto_date and date is None:
        date = datetime.now()
    if title is None and "title" not in data:
        title = path.stem.replace("-", " ").replace("_", " ").title()

    ensure_dir(path)
    content = write_frontmatter(data, body, title=title, date=date)
    path.write_text(content, encoding="utf-8")
    return path


def file_exists(path: Path) -> bool:
    """Return True if the file exists."""
    return path.exists()


def get_file_mtime(path: Path) -> Optional[datetime]:
    """Return the file's mtime as a datetime, or None if not found."""
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime)
