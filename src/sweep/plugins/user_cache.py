"""Plugin to clean ~/.cache contents."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.utils import dir_info, xdg_cache_home

log = logging.getLogger(__name__)

# Directories commonly used by active applications that should not be cleaned
_EXCLUDE_DIRS = {
    "fontconfig",
    "icon-cache.kcache",
    "gstreamer-1.0",
    "babl",
    "gegl-0.4",
}


def _has_any_file(path: Path | str) -> bool:
    """Check if a directory tree contains any regular file with non-zero size."""
    stack: list[Path | str] = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            if entry.stat(follow_symlinks=False).st_size > 0:
                                return True
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except OSError:
                        continue
        except OSError:
            pass
    return False


class UserCachePlugin(CleanPlugin):
    """Cleans user cache directory (~/.cache) excluding active app caches."""

    id = "user_cache"
    name = "User Cache"
    _count_files = True
    description = (
        "Removes cached files from ~/.cache. Excludes critical caches like "
        "font and shader caches. Applications will regenerate these files as needed."
    )
    category = "user"
    sort_order = 40
    risk_level = "moderate"
    icon = "user-home-symbolic"

    # Populated by plugin_loader after all plugins are registered.
    # Contains top-level cache dir names managed by dedicated plugins.
    _managed_by_plugins: set[str] = set()

    def _is_excluded(self, name: str) -> bool:
        """Check if a cache directory should be skipped."""
        return name in _EXCLUDE_DIRS or name in self._managed_by_plugins

    def _cache_dir(self) -> Path:
        return xdg_cache_home()

    @property
    def unavailable_reason(self) -> str | None:
        if not self._cache_dir().is_dir():
            return "User cache directory not found"
        return None

    def has_items(self) -> bool:
        try:
            for item in self._cache_dir().iterdir():
                if self._is_excluded(item.name):
                    continue
                try:
                    if item.is_dir():
                        if _has_any_file(item):
                            return True
                    elif item.stat().st_size > 0:
                        return True
                except OSError:
                    continue
            return False
        except OSError:
            return False

    def scan(self) -> ScanResult:
        cache_dir = self._cache_dir()
        entries: list[FileEntry] = []
        total = 0

        for item in sorted(cache_dir.iterdir()):
            if self._is_excluded(item.name):
                continue
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
                            description=f"Cache: {item.name}",
                            is_leaf=True,
                            file_count=fcount,
                        )
                    )
                    total += size
            except OSError:
                log.debug("Cannot access: %s", item)

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} cache directories totaling {total} bytes",
        )
