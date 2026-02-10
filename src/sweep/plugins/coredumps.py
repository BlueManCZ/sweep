"""Plugin to clean systemd coredumps."""

from __future__ import annotations

import logging
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.utils import remove_entries

log = logging.getLogger(__name__)

_COREDUMP_DIR = Path("/var/lib/systemd/coredump")


class CoredumpsPlugin(CleanPlugin):
    """Cleans systemd coredump files."""

    id = "coredumps"
    name = "Core Dumps"
    description = (
        "Removes systemd core dump files from /var/lib/systemd/coredump. "
        "These are crash snapshots typically only useful for debugging."
    )
    category = "system"
    icon = "dialog-warning-symbolic"
    requires_root = True

    @property
    def unavailable_reason(self) -> str | None:
        if not _COREDUMP_DIR.is_dir():
            return "Systemd coredump directory not found"
        return None

    def has_items(self) -> bool:
        try:
            return any(_COREDUMP_DIR.iterdir())
        except OSError:
            return False

    def scan(self) -> ScanResult:
        entries: list[FileEntry] = []
        total = 0

        if _COREDUMP_DIR.is_dir():
            for item in sorted(_COREDUMP_DIR.iterdir()):
                try:
                    size = item.stat().st_size
                    if size > 0:
                        entries.append(
                            FileEntry(
                                path=item,
                                size_bytes=size,
                                description=f"Core dump: {item.name}",
                                file_count=1,
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
            summary=f"Found {len(entries)} core dump files totaling {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        freed, removed, errors = remove_entries(entries)
        return CleanResult(plugin_id=self.id, freed_bytes=freed, errors=errors, files_removed=removed)
