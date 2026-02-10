"""Plugin to clean pacman package cache.

Works with or without ``paccache`` (from ``pacman-contrib``).  When
``paccache`` is available it is used for accurate per-package version
tracking.  Otherwise the plugin groups cached packages by name using
``pacman -Q`` and file modification time, keeping the 3 most recent
versions of each package.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.utils import dir_size, has_command, remove_entries

log = logging.getLogger(__name__)

_PACMAN_CACHE_DIR = Path("/var/cache/pacman/pkg")
_KEEP_VERSIONS = 3

# Matches pacman package filenames: <name>-<ver>-<rel>-<arch>.pkg.tar.*
_PKG_RE = re.compile(r"^(.+)-[^-]+-[^-]+-[^-]+\.pkg\.tar(?:\.\w+)?$")


def _find_removable_packages() -> list[Path]:
    """Group cached packages by name and return those beyond the 3 newest."""
    groups: dict[str, list[tuple[float, Path]]] = defaultdict(list)

    try:
        with os.scandir(_PACMAN_CACHE_DIR) as it:
            for entry in it:
                if not entry.is_file(follow_symlinks=False):
                    continue
                m = _PKG_RE.match(entry.name)
                if not m:
                    continue
                pkg_name = m.group(1)
                try:
                    mtime = entry.stat(follow_symlinks=False).st_mtime
                except OSError:
                    continue
                groups[pkg_name].append((mtime, Path(entry.path)))
    except OSError:
        return []

    removable: list[Path] = []
    for files in groups.values():
        if len(files) <= _KEEP_VERSIONS:
            continue
        # Sort newest first, mark the rest for removal
        files.sort(key=lambda x: x[0], reverse=True)
        removable.extend(path for _, path in files[_KEEP_VERSIONS:])

    return removable


class PacmanCachePlugin(CleanPlugin):
    """Cleans old pacman package cache, keeping the 3 most recent versions."""

    id = "pacman_cache"
    name = "Pacman Cache"
    description = (
        "Removes old package versions from the pacman cache, keeping the " "3 most recent versions of each package."
    )
    category = "package_manager"
    icon = "system-software-install-symbolic"
    requires_root = True
    risk_level = "moderate"

    @property
    def unavailable_reason(self) -> str | None:
        if not _PACMAN_CACHE_DIR.is_dir():
            return "Pacman cache directory not found"
        return None

    def has_items(self) -> bool:
        try:
            return any(_PACMAN_CACHE_DIR.iterdir())
        except OSError:
            return False

    def scan(self) -> ScanResult:
        entries: list[FileEntry] = []
        total = 0

        if has_command("paccache"):
            entries, total = self._scan_paccache()
        else:
            entries, total = self._scan_native()

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} old package versions totaling {total} bytes",
        )

    def _scan_paccache(self) -> tuple[list[FileEntry], int]:
        """Scan using paccache --dryrun."""
        entries: list[FileEntry] = []
        total = 0
        try:
            result = subprocess.run(
                ["paccache", "-dvk3"],
                capture_output=True,
                text=True,
            )
            for line in result.stderr.splitlines():
                if line.startswith("==>") or not line.strip():
                    continue
                path = Path(line.strip())
                if path.exists():
                    try:
                        size = path.stat().st_size
                        entries.append(
                            FileEntry(
                                path=path,
                                size_bytes=size,
                                description=f"Package: {path.name}",
                                is_leaf=True,
                                file_count=1,
                            )
                        )
                        total += size
                    except OSError:
                        pass
        except (subprocess.CalledProcessError, FileNotFoundError):
            return self._scan_native()
        return entries, total

    def _scan_native(self) -> tuple[list[FileEntry], int]:
        """Scan by grouping cached packages and keeping the 3 newest."""
        entries: list[FileEntry] = []
        total = 0
        for path in _find_removable_packages():
            try:
                size = path.stat().st_size
                entries.append(
                    FileEntry(
                        path=path,
                        size_bytes=size,
                        description=f"Package: {path.name}",
                        is_leaf=True,
                        file_count=1,
                    )
                )
                total += size
            except OSError:
                pass
        return entries, total

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        if has_command("paccache"):
            return self._clean_paccache(entries)
        return self._clean_native(entries)

    def _clean_paccache(self, entries: list[FileEntry]) -> CleanResult:
        """Clean using paccache."""
        errors: list[str] = []
        size_before = dir_size(_PACMAN_CACHE_DIR)

        try:
            subprocess.run(
                ["paccache", "-rk3"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            errors.append(f"paccache failed: {e.stderr.strip()}")

        size_after = dir_size(_PACMAN_CACHE_DIR)
        freed = max(0, size_before - size_after)
        return CleanResult(
            plugin_id=self.id,
            freed_bytes=freed,
            errors=errors,
            files_removed=len(entries) if freed > 0 else 0,
        )

    def _clean_native(self, entries: list[FileEntry]) -> CleanResult:
        """Clean by removing the specific files identified during scan."""
        freed, removed, errors = remove_entries(entries)
        return CleanResult(
            plugin_id=self.id,
            freed_bytes=freed,
            errors=errors,
            files_removed=removed,
        )
