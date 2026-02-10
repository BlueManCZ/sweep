"""Plugin to clean APT package cache."""

from __future__ import annotations

import logging
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.utils import command_clean

log = logging.getLogger(__name__)

_APT_CACHE_DIR = Path("/var/cache/apt/archives")


class AptCachePlugin(CleanPlugin):
    """Cleans downloaded APT package files."""

    id = "apt_cache"
    name = "APT Package Cache"
    description = (
        "Removes downloaded .deb package files from /var/cache/apt/archives. "
        "These are no longer needed after installation."
    )
    category = "package_manager"
    icon = "system-software-install-symbolic"
    requires_root = True

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
        return command_clean(self.id, ["apt-get", "clean"], _APT_CACHE_DIR, entries)
