"""Plugin to detect archive files that have already been extracted in Downloads."""

from __future__ import annotations

import logging
from pathlib import Path

from sweep.models.plugin import CleanPlugin, PluginGroup
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.plugins.download_duplicates import _get_downloads_dir

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

    id = "extracted_archives"
    name = "Extracted Archives"
    description = "Archive files with a matching extracted directory in Downloads"
    category = "user"
    group = _GROUP
    icon = "package-x-generic-symbolic"
    risk_level = "safe"
    sort_order = 41
    item_noun = "archive"

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
