"""Plugin to clean DNF package cache."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.utils import dir_info, dir_size, has_command

log = logging.getLogger(__name__)

_DNF_CACHE_DIR = Path("/var/cache/dnf")


class DnfCachePlugin(CleanPlugin):
    """Cleans DNF package manager cache."""

    id = "dnf_cache"
    name = "DNF Cache"
    description = "Removes cached DNF metadata and packages. " "DNF will re-download metadata when needed."
    category = "package_manager"
    icon = "system-software-install-symbolic"
    requires_root = True

    @property
    def unavailable_reason(self) -> str | None:
        if not has_command("dnf"):
            return "dnf command not found"
        if not _DNF_CACHE_DIR.is_dir():
            return "DNF cache directory not found"
        return None

    def has_items(self) -> bool:
        try:
            return any(_DNF_CACHE_DIR.iterdir())
        except OSError:
            return False

    def scan(self) -> ScanResult:
        size, fcount = dir_info(_DNF_CACHE_DIR)
        entries: list[FileEntry] = []
        if size > 0:
            entries.append(
                FileEntry(
                    path=_DNF_CACHE_DIR,
                    size_bytes=size,
                    description="DNF package cache",
                    file_count=fcount,
                )
            )

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=size,
            summary=f"DNF cache: {size} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        errors: list[str] = []
        size_before = dir_size(_DNF_CACHE_DIR)

        try:
            subprocess.run(
                ["dnf", "clean", "all"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            errors.append(f"dnf clean failed: {e.stderr.strip()}")

        size_after = dir_size(_DNF_CACHE_DIR)
        freed = max(0, size_before - size_after)

        return CleanResult(
            plugin_id=self.id, freed_bytes=freed, errors=errors, files_removed=len(entries) if freed > 0 else 0
        )
