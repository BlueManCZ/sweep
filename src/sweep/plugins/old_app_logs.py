"""Plugin to clean stale application log files in /var/log."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from sweep.models.clean_result import CleanResult
from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.utils import remove_entries

log = logging.getLogger(__name__)

_LOG_DIR = Path("/var/log")
_MAX_AGE_DAYS = 90

_SKIP_NAMES = frozenset({
    "syslog", "messages", "kern.log", "auth.log",
    "wtmp", "btmp", "lastlog", "faillog",
    "boot", ".keep",
})


class OldAppLogsPlugin(CleanPlugin):
    """Cleans stale standalone log files in /var/log older than 90 days."""

    @property
    def id(self) -> str:
        return "old_app_logs"

    @property
    def name(self) -> str:
        return "Old Application Logs"

    @property
    def description(self) -> str:
        return "Removes log files in /var/log not modified in over 90 days."

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
        return "moderate"

    @property
    def item_noun(self) -> str:
        return "log"

    @property
    def unavailable_reason(self) -> str | None:
        if not _LOG_DIR.is_dir():
            return "/var/log directory not found"
        return None

    def _is_rotated(self, name: str) -> bool:
        """Check if filename looks like a rotated log (e.g. syslog.1, auth.log.2.gz)."""
        parts = name.split(".")
        return any(part.isdigit() for part in parts)

    def _stale_files(self) -> list[Path]:
        cutoff = time.time() - _MAX_AGE_DAYS * 86400
        result: list[Path] = []

        try:
            for path in _LOG_DIR.iterdir():
                try:
                    if not path.is_file(follow_symlinks=False):
                        continue
                    if path.name in _SKIP_NAMES:
                        continue
                    if self._is_rotated(path.name):
                        continue
                    if path.stat().st_mtime < cutoff:
                        result.append(path)
                except OSError:
                    log.debug("Cannot access: %s", path)
        except OSError:
            log.debug("Cannot read %s", _LOG_DIR)

        return result

    def has_items(self) -> bool:
        try:
            return len(self._stale_files()) > 0
        except OSError:
            return False

    def scan(self) -> ScanResult:
        entries: list[FileEntry] = []
        total = 0

        for path in sorted(self._stale_files()):
            try:
                size = path.stat().st_size
                entries.append(FileEntry(
                    path=path,
                    size_bytes=size,
                    description=f"Stale log: {path.name}",
                    file_count=1,
                ))
                total += size
            except OSError:
                log.debug("Cannot stat: %s", path)

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} stale log files totaling {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        freed, removed, errors = remove_entries(entries)
        return CleanResult(
            plugin_id=self.id,
            freed_bytes=freed,
            files_removed=removed,
            errors=errors,
        )
