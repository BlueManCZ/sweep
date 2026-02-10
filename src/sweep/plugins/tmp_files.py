"""Plugin to clean user-owned temp files in /tmp."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.utils import dir_info

log = logging.getLogger(__name__)

_ONE_DAY = 86400  # seconds


class TmpFilesPlugin(CleanPlugin):
    """Cleans user-owned files in /tmp that are older than 1 day."""

    id = "tmp_files"
    name = "Temporary Files"
    _count_files = True
    description = (
        "Removes user-owned temporary files in /tmp older than 1 day. "
        "Active applications may still be using recent temp files."
    )
    category = "user"
    sort_order = 30
    icon = "edit-clear-symbolic"

    def has_items(self) -> bool:
        uid = os.getuid()
        cutoff = time.time() - _ONE_DAY
        try:
            for item in Path("/tmp").iterdir():
                try:
                    stat = item.lstat()
                    if stat.st_uid == uid and stat.st_mtime <= cutoff:
                        return True
                except OSError:
                    pass
        except OSError:
            pass
        return False

    def scan(self) -> ScanResult:
        entries: list[FileEntry] = []
        total = 0
        uid = os.getuid()
        cutoff = time.time() - _ONE_DAY

        for item in Path("/tmp").iterdir():
            try:
                stat = item.lstat()
                if stat.st_uid != uid:
                    continue
                if stat.st_mtime > cutoff:
                    continue
                if item.is_dir():
                    size, fcount = dir_info(item)
                else:
                    size, fcount = stat.st_size, 1
                entries.append(
                    FileEntry(
                        path=item, size_bytes=size, description=f"Temp: {item.name}", is_leaf=True, file_count=fcount
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
            summary=f"Found {len(entries)} old temp files totaling {total} bytes",
        )
