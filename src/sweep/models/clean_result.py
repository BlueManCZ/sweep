"""Cleaning result dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CleanResult:
    """Result of a cleaning operation."""

    plugin_id: str
    freed_bytes: int = 0
    errors: list[str] = field(default_factory=list)
    files_removed: int = 0
