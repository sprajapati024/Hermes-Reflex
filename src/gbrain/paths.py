"""Path resolver for GBrain/Reflex file structure."""

from pathlib import Path
from datetime import datetime
from typing import Optional
import os


# Default root — override via HERMES_REFLEX_GBRAIN_PATH env var
DEFAULT_GBRAIN_ROOT = Path.home() / "gbrain"


def get_gbrain_root() -> Path:
    """Return the GBrain root path."""
    return Path(os.environ.get("HERMES_REFLEX_GBRAIN_ROOT", str(DEFAULT_GBRAIN_ROOT)))


def get_reflex_root() -> Path:
    """Return the reflex root path."""
    return get_gbrain_root() / "reflex"


def get_contracts_root() -> Path:
    return get_reflex_root() / "contracts"


def get_checkins_root() -> Path:
    return get_reflex_root() / "checkins"


def get_signals_root() -> Path:
    return get_reflex_root() / "signals"


def get_decisions_root() -> Path:
    return get_reflex_root() / "decisions"


def get_patterns_root() -> Path:
    return get_reflex_root() / "patterns"


def get_experiments_root() -> Path:
    return get_reflex_root() / "experiments"


def get_interventions_root() -> Path:
    return get_reflex_root() / "interventions"


def get_overrides_root() -> Path:
    return get_reflex_root() / "overrides"


def get_reviews_root() -> Path:
    return get_reflex_root() / "reviews"


def get_skillify_root() -> Path:
    return get_reflex_root() / "skillify-candidates"


def get_embeddings_root() -> Path:
    return get_reflex_root() / "embeddings"


def get_embeddings_index_path() -> Path:
    """Return the SQLite embedding index path."""
    path = os.environ.get("HERMES_REFLEX_INDEX_PATH")
    if path:
        return Path(path)
    return get_embeddings_root() / "index.sqlite"


def get_embeddings_manifest_path() -> Path:
    """Return the embedding manifest JSON path."""
    path = os.environ.get("HERMES_REFLEX_MANIFEST_PATH")
    if path:
        return Path(path)
    return get_embeddings_root() / "manifest.json"


def get_current_contract_path() -> Path:
    return get_contracts_root() / "current-operating-contract.md"


def get_checkin_path(dt: Optional[datetime] = None) -> Path:
    """Return path for a checkin file. Creates YYYY/MM subdirs."""
    if dt is None:
        dt = datetime.now()
    root = get_checkins_root()
    year_dir = root / str(dt.year)
    month_dir = year_dir / f"{dt.month:02d}"
    return month_dir / f"{dt.strftime('%Y-%m-%d')}.md"


def get_signal_path(dt: Optional[datetime] = None) -> Path:
    if dt is None:
        dt = datetime.now()
    root = get_signals_root()
    year_dir = root / str(dt.year)
    month_dir = year_dir / f"{dt.month:02d}"
    return month_dir / f"{dt.strftime('%Y-%m-%d')}.md"


def get_decision_path(dt: Optional[datetime] = None) -> Path:
    if dt is None:
        dt = datetime.now()
    root = get_decisions_root()
    year_dir = root / str(dt.year)
    month_dir = year_dir / f"{dt.month:02d}"
    return month_dir / f"{dt.strftime('%Y-%m-%d')}.md"


def get_experiment_path(experiment_id: str, status: str = "active") -> Path:
    """Return path for an experiment file."""
    return get_experiments_root() / status / f"{experiment_id}.md"


def get_intervention_path(dt: Optional[datetime] = None) -> Path:
    if dt is None:
        dt = datetime.now()
    root = get_interventions_root()
    year_dir = root / str(dt.year)
    month_dir = year_dir / f"{dt.month:02d}"
    return month_dir / f"{dt.strftime('%Y-%m-%d')}.md"


def get_override_path(dt: Optional[datetime] = None) -> Path:
    if dt is None:
        dt = datetime.now()
    root = get_overrides_root()
    year_dir = root / str(dt.year)
    month_dir = year_dir / f"{dt.month:02d}"
    return month_dir / f"{dt.strftime('%Y-%m-%d')}.md"


def get_weekly_review_path(year: int, week: int) -> Path:
    """Return path for a weekly review. ISO week."""
    root = get_reviews_root() / "weekly"
    return root / str(year) / f"{year}-W{week:02d}.md"


def get_pattern_path(pattern_id: str, status: str = "active") -> Path:
    """Return path for a pattern file."""
    return get_patterns_root() / status / f"{pattern_id}.md"


def get_skillify_candidate_path(candidate_id: str) -> Path:
    return get_skillify_root() / f"{candidate_id}.md"


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, create if missing. Returns the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
