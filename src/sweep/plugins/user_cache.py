"""Plugin to clean ~/.cache contents."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.utils import dir_info, remove_entries, xdg_cache_home

log = logging.getLogger(__name__)

# Directories commonly used by active applications that should not be cleaned
_EXCLUDE_DIRS = {
    "fontconfig",
    "icon-cache.kcache",
    "gstreamer-1.0",
    "babl",
    "gegl-0.4",
}

# Handled by dedicated plugins
_PLUGIN_DIRS = {
    "thumbnails",
    "mozilla",
    "chromium",
    "google-chrome",
    "opera",
    "zen",
    "BraveSoftware",
    "microsoft-edge",
    "electron",
    "darktable",
    "Google",
    "JetBrains",
    "pip",
    "pipenv",
    "uv",
    "pypoetry",
    "virtualenv",
    ".vpython-root",
    "yarn",
    "pnpm",
    "typescript",
    "biome",
    "black",
    "node-gyp",
    "nvidia",
    "mesa_shader_cache",
    "mesa_shader_cache_db",
    "ms-playwright",
    "Cypress",
    "electron-builder",
    "spotify",
    "github-copilot",
    "strawberry",
    "unity3d",
    "whatsapp-for-linux",
    "wine",
    "winetricks",
    "protontricks",
    "thunderbird",
    "evolution",
    "geary",
    "epiphany",
    "pylint",
    "tracker",
    "tracker3",
}

# Prefixes handled by dedicated plugins (directories with dynamic suffixes)
_PLUGIN_DIR_PREFIXES = ("vpython-root.",)


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


def _is_excluded(name: str) -> bool:
    """Check if a cache directory should be skipped."""
    return name in _EXCLUDE_DIRS or name in _PLUGIN_DIRS or name.startswith(_PLUGIN_DIR_PREFIXES)


class UserCachePlugin(CleanPlugin):
    """Cleans user cache directory (~/.cache) excluding active app caches."""

    @property
    def id(self) -> str:
        return "user_cache"

    @property
    def name(self) -> str:
        return "User Cache"

    @property
    def description(self) -> str:
        return (
            "Removes cached files from ~/.cache. Excludes critical caches like "
            "font and shader caches. Applications will regenerate these files as needed."
        )

    @property
    def category(self) -> str:
        return "user"

    @property
    def sort_order(self) -> int:
        return 40

    @property
    def risk_level(self) -> str:
        return "moderate"

    @property
    def icon(self) -> str:
        return "user-home-symbolic"

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
                if _is_excluded(item.name):
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
            if _is_excluded(item.name):
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

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        freed, removed, errors = remove_entries(entries, count_files=True)
        return CleanResult(plugin_id=self.id, freed_bytes=freed, errors=errors, files_removed=removed)
