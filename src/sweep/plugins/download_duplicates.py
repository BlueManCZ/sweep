"""Plugin to detect duplicate files in the Downloads directory."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from sweep.models.plugin import CleanPlugin, PluginGroup
from sweep.models.scan_result import FileEntry, ScanResult

log = logging.getLogger(__name__)

_GROUP = PluginGroup("downloads", "Downloads Cleanup", "Duplicates and extracted archives in ~/Downloads")

_CHUNK_SIZE = 65_536  # 64 KB


def _get_downloads_dir() -> Path | None:
    """Resolve the user's Downloads directory.

    Reads ``XDG_DOWNLOAD_DIR`` from ``~/.config/user-dirs.dirs``,
    falls back to ``~/Downloads``.  Returns *None* when the directory
    does not exist.
    """
    dirs_file = Path.home() / ".config" / "user-dirs.dirs"
    downloads = None

    if dirs_file.is_file():
        try:
            text = dirs_file.read_text()
            match = re.search(r'^XDG_DOWNLOAD_DIR="(.+)"', text, re.MULTILINE)
            if match:
                raw = match.group(1).replace("$HOME", str(Path.home()))
                downloads = Path(raw)
        except OSError:
            pass

    if downloads is None:
        downloads = Path.home() / "Downloads"

    return downloads if downloads.is_dir() else None


def _sha256(path: Path) -> str:
    """Compute SHA-256 of a file using chunked reads."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


class DownloadDuplicatesPlugin(CleanPlugin):
    """Finds files with identical content in Downloads and offers to remove copies."""

    id = "download_duplicates"
    name = "Duplicate Files"
    description = "Files with identical content in Downloads — keeps the oldest copy"
    category = "user"
    group = _GROUP
    icon = "edit-copy-symbolic"
    risk_level = "moderate"
    sort_order = 40
    item_noun = "file"

    @property
    def unavailable_reason(self) -> str | None:
        if _get_downloads_dir() is None:
            return "Downloads directory not found"
        return None

    def scan(self) -> ScanResult:
        downloads = _get_downloads_dir()
        if downloads is None:
            return ScanResult(plugin_id=self.id, plugin_name=self.name)

        # Group regular files by size.
        by_size: dict[int, list[Path]] = {}
        try:
            for item in downloads.iterdir():
                try:
                    if item.is_file() and not item.is_symlink():
                        size = item.stat().st_size
                        if size > 0:
                            by_size.setdefault(size, []).append(item)
                except OSError:
                    log.debug("Cannot stat: %s", item)
        except OSError:
            log.debug("Cannot list Downloads directory: %s", downloads)
            return ScanResult(plugin_id=self.id, plugin_name=self.name)

        # For same-size groups, hash and find true duplicates.
        entries: list[FileEntry] = []
        total = 0

        for size, paths in by_size.items():
            if len(paths) < 2:
                continue

            by_hash: dict[str, list[Path]] = {}
            for p in paths:
                try:
                    digest = _sha256(p)
                    by_hash.setdefault(digest, []).append(p)
                except OSError:
                    log.debug("Cannot hash: %s", p)

            for duplicates in by_hash.values():
                if len(duplicates) < 2:
                    continue
                # Keep the oldest file (lowest mtime).
                duplicates.sort(key=lambda p: p.stat().st_mtime)
                kept = duplicates[0]
                for dup in duplicates[1:]:
                    entries.append(
                        FileEntry(
                            path=dup,
                            size_bytes=size,
                            description=f"Duplicate of: {kept.name}",
                            is_leaf=True,
                            file_count=1,
                        )
                    )
                    total += size

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} duplicate files totaling {total} bytes",
        )
