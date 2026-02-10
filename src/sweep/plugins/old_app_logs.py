"""Plugin to clean stale application log files in /var/log."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult

log = logging.getLogger(__name__)

_LOG_DIR = Path("/var/log")
_MAX_AGE_DAYS = 90

_SKIP_NAMES = frozenset(
    {
        "syslog",
        "messages",
        "kern.log",
        "auth.log",
        "wtmp",
        "btmp",
        "lastlog",
        "faillog",
        "boot",
        ".keep",
    }
)


class OldAppLogsPlugin(CleanPlugin):
    """Cleans stale standalone log files in /var/log older than 90 days."""

    id = "old_app_logs"
    name = "Old Application Logs"
    description = "Removes log files in /var/log not modified in over 90 days."
    category = "system"
    icon = "text-x-generic-symbolic"
    requires_root = True
    risk_level = "moderate"
    item_noun = "log"

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
                    if path.is_symlink() or not path.is_file():
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
                st = path.stat()
                size = st.st_size
                modified = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d")
                entries.append(
                    FileEntry(
                        path=path,
                        size_bytes=size,
                        description=f"Last modified: {modified}",
                        is_leaf=True,
                        file_count=1,
                    )
                )
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
