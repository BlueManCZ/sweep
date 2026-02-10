"""Plugin to clean thumbnail cache."""

from __future__ import annotations

import logging
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.utils import dir_info, remove_entries, xdg_cache_home

log = logging.getLogger(__name__)


class ThumbnailsPlugin(CleanPlugin):
    """Cleans the freedesktop thumbnail cache (~/.cache/thumbnails)."""

    @property
    def id(self) -> str:
        return "thumbnails"

    @property
    def name(self) -> str:
        return "Thumbnails"

    @property
    def description(self) -> str:
        return (
            "Removes cached thumbnail images. File managers and image viewers "
            "will regenerate thumbnails when browsing directories."
        )

    @property
    def category(self) -> str:
        return "user"

    @property
    def sort_order(self) -> int:
        return 20

    @property
    def icon(self) -> str:
        return "image-x-generic-symbolic"

    def _thumb_dir(self) -> Path:
        return xdg_cache_home() / "thumbnails"

    @property
    def unavailable_reason(self) -> str | None:
        if not self._thumb_dir().is_dir():
            return "Thumbnail cache not found"
        return None

    def has_items(self) -> bool:
        try:
            return any(self._thumb_dir().iterdir())
        except OSError:
            return False

    def scan(self) -> ScanResult:
        thumb_dir = self._thumb_dir()
        entries: list[FileEntry] = []
        total = 0

        for item in sorted(thumb_dir.iterdir()):
            try:
                if item.is_dir():
                    size, fcount = dir_info(item)
                else:
                    size, fcount = item.stat().st_size, 1
                if size > 0:
                    entries.append(
                        FileEntry(path=item, size_bytes=size, description=f"Thumbnails: {item.name}", file_count=fcount)
                    )
                    total += size
            except OSError:
                log.debug("Cannot access: %s", item)

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} thumbnail directories totaling {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        freed, removed, errors = remove_entries(entries, count_files=True)
        return CleanResult(plugin_id=self.id, freed_bytes=freed, errors=errors, files_removed=removed)
