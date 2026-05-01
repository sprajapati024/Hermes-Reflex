"""Configuration loader for Hermes Reflex.

Loads config.yaml from the project root. Paths are resolved relative to
the location of this file's parent directory.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml

_CONFIG: Optional[dict[str, Any]] = None

# Cache the project root (src/core/ -> project root)
_PROJECT_ROOT: Optional[Path] = None


def _get_project_root() -> Path:
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        # src/core/config.py -> src/core/ -> project root
        _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    return _PROJECT_ROOT


def load_config() -> dict[str, Any]:
    """Load and cache config.yaml from the project root."""
    global _CONFIG
    if _CONFIG is None:
        config_path = _get_project_root() / "config.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"config.yaml not found at {config_path}")
        with open(config_path) as f:
            _CONFIG = yaml.safe_load(f)
    return _CONFIG


def get_config() -> dict[str, Any]:
    """Alias for load_config()."""
    return load_config()
