"""Plugin to clean the wtmp login records file."""

from __future__ import annotations

import logging
from pathlib import Path

from sweep.models.clean_result import CleanResult
from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult

log = logging.getLogger(__name__)

_WTMP = Path("/var/log/wtmp")
_THRESHOLD = 1 * 1024 * 1024  # 1 MB


class LoginRecordsPlugin(CleanPlugin):
    """Truncates /var/log/wtmp when it grows beyond 1 MB."""

    id = "login_records"
    name = "Login Records"
    description = (
        "Truncates /var/log/wtmp, the binary log of all login/logout "
        "events. The file is truncated (not deleted) so the 'last' "
        "command continues to work."
    )
    category = "system"
    icon = "system-users-symbolic"
    requires_root = True
    risk_level = "moderate"
    item_noun = "record"

    @property
    def unavailable_reason(self) -> str | None:
        if not _WTMP.exists():
            return "/var/log/wtmp not found"
        return None

    def has_items(self) -> bool:
        try:
            return _WTMP.stat().st_size > _THRESHOLD
        except OSError:
            return False

    def scan(self) -> ScanResult:
        entries: list[FileEntry] = []
        total = 0

        try:
            size = _WTMP.stat().st_size
            if size > _THRESHOLD:
                reclaimable = size - _THRESHOLD
                entries.append(
                    FileEntry(
                        path=_WTMP,
                        size_bytes=reclaimable,
                        description=f"Login records ({size} bytes, keeping 1 MB)",
                        is_leaf=True,
                        file_count=1,
                    )
                )
                total = reclaimable
        except OSError:
            log.debug("Cannot stat %s", _WTMP)

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"wtmp: {total} bytes reclaimable",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        errors: list[str] = []
        freed = 0

        for entry in entries:
            try:
                size_before = entry.path.stat().st_size
                with open(entry.path, "wb"):
                    pass  # truncate to 0 bytes
                freed += size_before
            except OSError as e:
                errors.append(f"{entry.path}: {e}")

        return CleanResult(
            plugin_id=self.id,
            freed_bytes=freed,
            files_removed=0,
            errors=errors,
        )
