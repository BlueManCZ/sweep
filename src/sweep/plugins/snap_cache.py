"""Plugin to clean old snap revisions."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.utils import has_command

log = logging.getLogger(__name__)


class SnapCachePlugin(CleanPlugin):
    """Removes old snap revisions, keeping only the current one."""

    @property
    def id(self) -> str:
        return "snap_cache"

    @property
    def name(self) -> str:
        return "Old Snap Revisions"

    @property
    def description(self) -> str:
        return (
            "Removes old snap package revisions. Snap keeps previous revisions "
            "for rollback; this removes all but the currently active revision."
        )

    @property
    def category(self) -> str:
        return "package_manager"

    @property
    def icon(self) -> str:
        return "application-x-addon-symbolic"

    @property
    def requires_root(self) -> bool:
        return True

    @property
    def item_noun(self) -> str:
        return "snap"

    @property
    def unavailable_reason(self) -> str | None:
        if not has_command("snap"):
            return "Snap not installed"
        if not Path("/var/lib/snapd/snaps").is_dir():
            return "snapd not configured"
        return None

    def scan(self) -> ScanResult:
        entries: list[FileEntry] = []
        total = 0

        try:
            # List disabled (old) snap revisions
            result = subprocess.run(
                ["snap", "list", "--all"],
                capture_output=True,
                text=True,
            )
            for line in result.stdout.splitlines()[1:]:  # skip header
                parts = line.split()
                if len(parts) >= 6 and "disabled" in parts:
                    snap_name = parts[0]
                    revision = parts[2]
                    snap_file = Path(f"/var/lib/snapd/snaps/{snap_name}_{revision}.snap")
                    if snap_file.exists():
                        try:
                            size = snap_file.stat().st_size
                            entries.append(FileEntry(
                                path=snap_file,
                                size_bytes=size,
                                description=f"Snap: {snap_name} rev {revision}",
                                file_count=1,
                            ))
                            total += size
                        except OSError:
                            pass
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} old snap revisions totaling {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        freed = 0
        removed = 0
        errors: list[str] = []

        for entry in entries:
            # Extract snap name and revision from path
            stem = entry.path.stem  # e.g., "firefox_1234"
            parts = stem.rsplit("_", 1)
            if len(parts) != 2:
                errors.append(f"Cannot parse snap file: {entry.path}")
                continue

            snap_name, revision = parts
            try:
                subprocess.run(
                    ["snap", "remove", snap_name, "--revision", revision],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                freed += entry.size_bytes
                removed += 1
            except subprocess.CalledProcessError as e:
                errors.append(f"snap remove {snap_name} rev {revision}: {e.stderr.strip()}")

        return CleanResult(plugin_id=self.id, freed_bytes=freed, errors=errors, files_removed=removed)
