"""Plugin to clean GNOME Tracker search index cache."""

from __future__ import annotations

import logging
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.utils import dir_info, xdg_cache_home

log = logging.getLogger(__name__)

# Tracker directory names (v2 and v3)
_TRACKER_DIRS = ("tracker", "tracker3")


class TrackerCachePlugin(CleanPlugin):
    """Cleans the GNOME Tracker file indexing cache."""

    id = "tracker_cache"
    name = "Tracker Search Index"
    _count_files = True
    description = (
        "Removes the Tracker file indexing database used for desktop search. "
        "Tracker will rebuild the index automatically in the background."
    )
    category = "user"
    sort_order = 21
    icon = "system-search-symbolic"

    def _tracker_dirs(self) -> list[Path]:
        cache = xdg_cache_home()
        return [cache / name for name in _TRACKER_DIRS if (cache / name).is_dir()]

    @property
    def unavailable_reason(self) -> str | None:
        if not self._tracker_dirs():
            return "Tracker cache not found"
        return None

    def has_items(self) -> bool:
        try:
            return any(any(d.iterdir()) for d in self._tracker_dirs())
        except OSError:
            return False

    def scan(self) -> ScanResult:
        entries: list[FileEntry] = []
        total = 0

        for tracker_dir in self._tracker_dirs():
            for item in sorted(tracker_dir.iterdir()):
                try:
                    if item.is_dir():
                        size, fcount = dir_info(item)
                    else:
                        size, fcount = item.stat().st_size, 1
                    if size > 0:
                        entries.append(
                            FileEntry(
                                path=item,
                                size_bytes=size,
                                description=f"Tracker: {item.parent.name}/{item.name}",
                                file_count=fcount,
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
            summary=f"Found {len(entries)} Tracker cache entries totaling {total} bytes",
        )
