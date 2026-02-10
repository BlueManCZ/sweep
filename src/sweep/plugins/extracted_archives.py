"""Plugin to detect archive files that have already been extracted in Downloads."""

from __future__ import annotations

import logging
from pathlib import Path

from sweep.models.clean_result import CleanResult
from sweep.models.plugin import CleanPlugin, PluginGroup
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.plugins.download_duplicates import _get_downloads_dir
from sweep.utils import remove_entries

log = logging.getLogger(__name__)

_GROUP = PluginGroup("downloads", "Downloads Cleanup", "Duplicates and extracted archives in ~/Downloads")

# Ordered longest-first so `.tar.gz` is checked before `.gz`.
_ARCHIVE_EXTENSIONS = (
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".tar.zst",
    ".zip",
    ".rar",
    ".7z",
)


def _strip_archive_ext(name: str) -> str | None:
    """Return the stem after removing a known archive extension, or None."""
    lower = name.lower()
    for ext in _ARCHIVE_EXTENSIONS:
        if lower.endswith(ext):
            return name[: len(name) - len(ext)]
    return None


class ExtractedArchivesPlugin(CleanPlugin):
    """Finds archive files whose contents have already been extracted alongside them."""

    @property
    def id(self) -> str:
        return "extracted_archives"

    @property
    def name(self) -> str:
        return "Extracted Archives"

    @property
    def description(self) -> str:
        return "Archive files with a matching extracted directory in Downloads"

    @property
    def category(self) -> str:
        return "user"

    @property
    def group(self) -> PluginGroup:
        return _GROUP

    @property
    def icon(self) -> str:
        return "package-x-generic-symbolic"

    @property
    def risk_level(self) -> str:
        return "safe"

    @property
    def sort_order(self) -> int:
        return 41

    @property
    def item_noun(self) -> str:
        return "archive"

    @property
    def unavailable_reason(self) -> str | None:
        if _get_downloads_dir() is None:
            return "Downloads directory not found"
        return None

    def scan(self) -> ScanResult:
        downloads = _get_downloads_dir()
        if downloads is None:
            return ScanResult(plugin_id=self.id, plugin_name=self.name)

        entries: list[FileEntry] = []
        total = 0

        try:
            for item in sorted(downloads.iterdir()):
                if not item.is_file() or item.is_symlink():
                    continue

                stem = _strip_archive_ext(item.name)
                if stem is None:
                    continue

                extracted_dir = downloads / stem
                if not extracted_dir.is_dir():
                    continue

                try:
                    size = item.stat().st_size
                except OSError:
                    log.debug("Cannot stat: %s", item)
                    continue

                entries.append(
                    FileEntry(
                        path=item,
                        size_bytes=size,
                        description=f"Extracted to: {stem}",
                        is_leaf=True,
                        file_count=1,
                    )
                )
                total += size
        except OSError:
            log.debug("Cannot list Downloads directory: %s", downloads)

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} extracted archives totaling {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        freed, removed, errors = remove_entries(entries)
        return CleanResult(
            plugin_id=self.id,
            freed_bytes=freed,
            files_removed=removed,
            errors=errors,
        )
