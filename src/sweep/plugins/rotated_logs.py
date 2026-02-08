"""Plugin to clean rotated system log files in /var/log."""

from __future__ import annotations

import logging
from pathlib import Path

from sweep.models.clean_result import CleanResult
from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.utils import remove_entries

log = logging.getLogger(__name__)

_LOG_DIR = Path("/var/log")

_ROTATED_PATTERNS = (
    "auth.log.[0-9]*",
    "kern.log.[0-9]*",
    "messages.[0-9]*",
    "syslog.[0-9]*",
)


class RotatedLogsPlugin(CleanPlugin):
    """Cleans rotated syslog files (*.0, *.N.gz) in /var/log."""

    @property
    def id(self) -> str:
        return "rotated_logs"

    @property
    def name(self) -> str:
        return "Rotated System Logs"

    @property
    def description(self) -> str:
        return (
            "Removes rotated log files (auth.log.1.gz, syslog.2.gz, etc.) "
            "in /var/log. The current log files are kept intact."
        )

    @property
    def category(self) -> str:
        return "system"

    @property
    def icon(self) -> str:
        return "text-x-generic-symbolic"

    @property
    def requires_root(self) -> bool:
        return True

    @property
    def risk_level(self) -> str:
        return "safe"

    @property
    def item_noun(self) -> str:
        return "log"

    @property
    def unavailable_reason(self) -> str | None:
        if not _LOG_DIR.is_dir():
            return "/var/log directory not found"
        return None

    def has_items(self) -> bool:
        try:
            return any(
                next(_LOG_DIR.glob(pattern), None) is not None
                for pattern in _ROTATED_PATTERNS
            )
        except OSError:
            return False

    def scan(self) -> ScanResult:
        entries: list[FileEntry] = []
        total = 0

        for pattern in _ROTATED_PATTERNS:
            try:
                for path in sorted(_LOG_DIR.glob(pattern)):
                    try:
                        if path.is_file():
                            size = path.stat().st_size
                            entries.append(FileEntry(
                                path=path,
                                size_bytes=size,
                                description=f"Rotated log: {path.name}",
                                file_count=1,
                            ))
                            total += size
                    except OSError:
                        log.debug("Cannot access: %s", path)
            except OSError:
                log.debug("Cannot glob %s in %s", pattern, _LOG_DIR)

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} rotated log files totaling {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        freed, removed, errors = remove_entries(entries)
        return CleanResult(
            plugin_id=self.id,
            freed_bytes=freed,
            files_removed=removed,
            errors=errors,
        )
