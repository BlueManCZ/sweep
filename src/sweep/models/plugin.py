"""Base plugin interface."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PluginGroup:
    """Display grouping for related plugins."""

    id: str
    name: str
    description: str = ""


class CleanPlugin(ABC):
    """Base class for all cleaning plugins.

    Every plugin must implement this interface to participate
    in scanning and cleaning operations.
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique identifier, e.g. 'apt_cache'."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name, e.g. 'APT Package Cache'."""

    @property
    @abstractmethod
    def description(self) -> str:
        """What this plugin cleans and why it's safe."""

    @property
    @abstractmethod
    def category(self) -> str:
        """Category: 'system', 'user', 'development', 'package_manager', 'browser', 'application'."""

    @property
    def group(self) -> PluginGroup | None:
        """Display group for related plugins. None means standalone."""
        return None

    @property
    def icon(self) -> str:
        """Icon name for display in the GUI."""
        return "application-x-executable-symbolic"

    @property
    def requires_root(self) -> bool:
        """Whether this plugin needs elevated privileges."""
        return False

    @property
    def risk_level(self) -> str:
        """Risk level: 'safe', 'moderate', or 'aggressive'."""
        return "safe"

    @property
    def sort_order(self) -> int:
        """Display order within category (lower = first). Default 50."""
        return 50

    @property
    def item_noun(self) -> str:
        """Singular noun for cleaned items, e.g. 'file', 'package', 'runtime'."""
        return "file"

    _count_files: bool = False
    """Whether to count individual files inside directories during clean."""

    @abstractmethod
    def scan(self) -> ScanResult:
        """Scan for cleanable files. MUST NOT delete anything."""

    def clean(self, entries: list[FileEntry] | None = None) -> CleanResult:
        """Remove files.

        If entries is None, clean everything from last scan.
        If entries is provided, clean only those specific items.
        Subclasses should override _do_clean() instead of this method.
        """
        if entries is None:
            entries = self.scan().entries
        return self._do_clean(entries)

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        """Remove the given file entries and return a CleanResult.

        The default implementation uses ``remove_entries()`` which handles
        both files and directories.  Override in subclasses that need
        custom clean logic (e.g. calling external commands).
        """
        from sweep.utils import remove_entries

        freed, removed, errors = remove_entries(entries, count_files=self._count_files)
        return CleanResult(
            plugin_id=self.id,
            freed_bytes=freed,
            files_removed=removed,
            errors=errors,
        )

    @property
    def unavailable_reason(self) -> str | None:
        """Why this plugin cannot work on this system, or None if supported."""
        return None

    def is_available(self) -> bool:
        """Check if this plugin is applicable on the current system."""
        return self.unavailable_reason is None

    def has_items(self) -> bool:
        """Quick check whether there is anything to clean right now."""
        return True


class SimpleCacheDirPlugin(CleanPlugin, ABC):
    """Base class for plugins that clean a single directory under ~/.cache.

    Subclasses only need to define metadata properties (id, name, description)
    and _cache_dir_name. All scan/clean/availability logic is provided.
    """

    _count_files = True

    @property
    @abstractmethod
    def _cache_dir_name(self) -> str:
        """Name of the directory under ~/.cache, e.g. 'electron'."""

    @property
    def _label(self) -> str:
        """Human-readable label for file descriptions. Defaults to name."""
        return self.name

    @property
    def category(self) -> str:
        return "application"

    def _cache_dir(self) -> Path:
        from sweep.utils import xdg_cache_home

        return xdg_cache_home() / self._cache_dir_name

    @property
    def unavailable_reason(self) -> str | None:
        if not self._cache_dir().is_dir():
            return f"{self._label} cache directory not found"
        return None

    def has_items(self) -> bool:
        try:
            return any(self._cache_dir().iterdir())
        except OSError:
            return False

    def scan(self) -> ScanResult:
        from sweep.utils import dir_info

        cache_dir = self._cache_dir()
        entries: list[FileEntry] = []
        total = 0

        try:
            for item in sorted(cache_dir.iterdir()):
                try:
                    if item.is_dir():
                        size, fcount = dir_info(item)
                    else:
                        size, fcount = item.stat().st_size, 1
                    if size > 0:
                        entries.append(
                            FileEntry(
                                path=item,
                                size_bytes=size,
                                description=f"{self._label} cache: {item.name}",
                                file_count=fcount,
                            )
                        )
                        total += size
                except OSError:
                    log.debug("Cannot access: %s", item)
        except OSError:
            log.debug("Cannot read %s cache directory: %s", self._label, cache_dir)

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} {self._label} cache entries totaling {total} bytes",
        )


class MultiDirPlugin(CleanPlugin, ABC):
    """Base class for plugins that clean one or more directories.

    Subclasses define metadata properties and _cache_dirs.
    All scan/clean/availability logic is provided.
    """

    @property
    @abstractmethod
    def _cache_dirs(self) -> tuple[Path, ...]:
        """Directories to clean."""

    @property
    def _recreate_dirs(self) -> bool:
        """Whether to recreate directories after cleaning."""
        return True

    @property
    def unavailable_reason(self) -> str | None:
        if not any(d.is_dir() for d in self._cache_dirs):
            return f"{self.name} not found"
        return None

    def has_items(self) -> bool:
        try:
            return any(d.is_dir() and any(d.iterdir()) for d in self._cache_dirs)
        except OSError:
            return False

    def scan(self) -> ScanResult:
        from sweep.utils import dir_info

        entries: list[FileEntry] = []
        total = 0

        for cache_dir in self._cache_dirs:
            if cache_dir.is_dir():
                size, fcount = dir_info(cache_dir)
                if size > 0:
                    entries.append(
                        FileEntry(
                            path=cache_dir,
                            size_bytes=size,
                            description=self.description,
                            file_count=fcount,
                        )
                    )
                    total += size

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {self.name}: {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        from sweep.utils import remove_entries

        freed, removed, errors = remove_entries(entries, count_files=True, recreate_dirs=self._recreate_dirs)
        return CleanResult(
            plugin_id=self.id,
            freed_bytes=freed,
            files_removed=removed,
            errors=errors,
        )
