"""Frontmatter parser and writer using python-frontmatter.

python-frontmatter parses and serialises YAML frontmatter in markdown files.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import frontmatter


def parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    """Parse frontmatter from a markdown string.

    Returns (frontmatter_dict, body_content).
    """
    post = frontmatter.loads(raw)
    return dict(post.metadata), post.content


def write_frontmatter(
    data: dict[str, Any],
    body: str,
    *,
    title: Optional[str] = None,
    date: Optional[datetime] = None,
) -> str:
    """Serialize frontmatter + body back to a markdown string.

    Args:
        data: Frontmatter dict.
        body: Markdown body content.
        title: Optional title to inject.
        date: Optional datetime injected as 'updated_at' ISO string.

    Returns:
        Full markdown string with frontmatter block.
    """
    front = dict(data)
    if title is not None:
        front["title"] = title
    if date is not None:
        front["updated_at"] = date.isoformat()

    post = frontmatter.Post(body.strip(), **front)
    return frontmatter.dumps(post)


def parse_date_from_frontmatter(data: dict[str, Any]) -> Optional[datetime]:
    """Extract a datetime from frontmatter, checking common field names."""
    for key in ("updated_at", "created_at", "date", "created", "modified"):
        val = data.get(key)
        if val is None:
            continue
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            for fmt in (
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    return datetime.fromisoformat(val)
                except ValueError:
                    pass
    return None


def extract_id_from_path(path: str) -> str:
    """Derive an ID from a file path, stripping status prefixes."""
    stem = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if stem.endswith(".md"):
        stem = stem[:-3]
    for prefix in ("candidate_", "watching_", "active_", "retired_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
    return stem
