"""Pipeline trace entry for verbose mode diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TraceEntry:
    stage: str        # e.g. "bypass_check"
    status: str       # e.g. "✅ Pass", "🚦 RISKY", "⏭ Skipped"
    detail: str       # human-readable explanation for this stage
    latency_ms: float # wall-clock ms spent in this stage
