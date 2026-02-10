"""Plugin to clean the user's trash."""

from __future__ import annotations

import logging
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.utils import dir_info, remove_entries, xdg_data_home

log = logging.getLogger(__name__)


class TrashPlugin(CleanPlugin):
    """Empties the user's trash directory (~/.local/share/Trash)."""

    @property
    def id(self) -> str:
        return "trash"

    @property
    def name(self) -> str:
        return "Trash"

    @property
    def description(self) -> str:
        return "Permanently deletes files in the trash. These files were already deleted by the user."

    @property
    def category(self) -> str:
        return "user"

    @property
    def sort_order(self) -> int:
        return 10

    @property
    def icon(self) -> str:
        return "user-trash-symbolic"

    def _trash_dir(self) -> Path:
        return xdg_data_home() / "Trash"

    @property
    def unavailable_reason(self) -> str | None:
        if not self._trash_dir().is_dir():
            return "Trash directory not found"
        return None

    def has_items(self) -> bool:
        try:
            files_dir = self._trash_dir() / "files"
            return files_dir.is_dir() and any(files_dir.iterdir())
        except OSError:
            return False

    def scan(self) -> ScanResult:
        trash_dir = self._trash_dir()
        entries: list[FileEntry] = []
        total = 0

        for subdir in (trash_dir / "files", trash_dir / "info"):
            if not subdir.is_dir():
                continue
            for item in sorted(subdir.iterdir()):
                try:
                    if item.is_dir():
                        size, fcount = dir_info(item)
                    else:
                        size, fcount = item.stat().st_size, 1
                    entries.append(
                        FileEntry(path=item, size_bytes=size, description=f"Trash: {item.name}", file_count=fcount)
                    )
                    total += size
                except OSError:
                    log.debug("Cannot access: %s", item)

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} items in trash totaling {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        freed, removed, errors = remove_entries(entries)
        return CleanResult(plugin_id=self.id, freed_bytes=freed, errors=errors, files_removed=removed)
