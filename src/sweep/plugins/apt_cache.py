"""Plugin to clean APT package cache."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.utils import dir_size

log = logging.getLogger(__name__)

_APT_CACHE_DIR = Path("/var/cache/apt/archives")


class AptCachePlugin(CleanPlugin):
    """Cleans downloaded APT package files."""

    @property
    def id(self) -> str:
        return "apt_cache"

    @property
    def name(self) -> str:
        return "APT Package Cache"

    @property
    def description(self) -> str:
        return (
            "Removes downloaded .deb package files from /var/cache/apt/archives. "
            "These are no longer needed after installation."
        )

    @property
    def category(self) -> str:
        return "package_manager"

    @property
    def icon(self) -> str:
        return "system-software-install-symbolic"

    @property
    def requires_root(self) -> bool:
        return True

    @property
    def unavailable_reason(self) -> str | None:
        if not _APT_CACHE_DIR.is_dir():
            return "APT not installed"
        return None

    def has_items(self) -> bool:
        try:
            return any(_APT_CACHE_DIR.glob("*.deb"))
        except OSError:
            return False

    def scan(self) -> ScanResult:
        entries: list[FileEntry] = []
        total = 0

        for item in sorted(_APT_CACHE_DIR.iterdir()):
            if item.suffix == ".deb":
                try:
                    size = item.stat().st_size
                    entries.append(
                        FileEntry(
                            path=item, size_bytes=size, description=f"Package: {item.name}", is_leaf=True, file_count=1
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
            summary=f"Found {len(entries)} cached packages totaling {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        errors: list[str] = []
        size_before = dir_size(_APT_CACHE_DIR)

        try:
            subprocess.run(
                ["apt-get", "clean"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            errors.append(f"apt-get clean failed: {e.stderr.strip()}")

        size_after = dir_size(_APT_CACHE_DIR)
        freed = max(0, size_before - size_after)

        return CleanResult(
            plugin_id=self.id, freed_bytes=freed, errors=errors, files_removed=len(entries) if freed > 0 else 0
        )
