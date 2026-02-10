"""Plugin to clean systemd journal logs."""

from __future__ import annotations

import logging
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.utils import command_clean, dir_info, has_command

log = logging.getLogger(__name__)

_JOURNAL_DIR = Path("/var/log/journal")


class JournalLogsPlugin(CleanPlugin):
    """Cleans old systemd journal logs using journalctl vacuum."""

    id = "journal_logs"
    name = "Journal Logs"
    description = (
        "Removes old systemd journal logs, keeping the most recent 100 MB. "
        "Logs are rotated automatically; older entries are rarely needed."
    )
    category = "system"
    icon = "text-x-generic-symbolic"
    requires_root = True
    item_noun = "log"

    @property
    def unavailable_reason(self) -> str | None:
        if not has_command("journalctl"):
            return "journalctl not found"
        if not _JOURNAL_DIR.is_dir():
            return "Journal directory not found"
        return None

    def scan(self) -> ScanResult:
        size, fcount = dir_info(_JOURNAL_DIR)
        # We'll vacuum down to 100M, so reclaimable is anything above that
        reclaimable = max(0, size - 100 * 1024 * 1024)
        entries: list[FileEntry] = []
        if reclaimable > 0:
            entries.append(
                FileEntry(
                    path=_JOURNAL_DIR,
                    size_bytes=reclaimable,
                    description="Systemd journal logs (keeping 100 MB)",
                    file_count=fcount,
                )
            )

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=reclaimable,
            summary=f"Journal logs: {reclaimable} bytes reclaimable",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        return command_clean(self.id, ["journalctl", "--vacuum-size=100M"], _JOURNAL_DIR, entries)
