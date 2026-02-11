"""Scan result dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class FileEntry:
    """Single file or directory that can be cleaned.

    Set ``is_leaf=True`` for entries that represent logical items
    (e.g. installed packages) rather than browsable filesystem paths.
    The UI will display these as atomic rows instead of expanding
    their path as a directory.
    """

    path: Path
    size_bytes: int
    description: str
    is_leaf: bool = False
    file_count: int = 0


@dataclass(slots=True)
class ScanResult:
    """Result of scanning for cleanable files."""

    plugin_id: str
    plugin_name: str
    entries: list[FileEntry] = field(default_factory=list)
    total_bytes: int = 0
    summary: str = ""
    error: str = ""
