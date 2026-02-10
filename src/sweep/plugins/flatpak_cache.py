"""Plugin to clean unused Flatpak runtimes."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.utils import has_command

log = logging.getLogger(__name__)


class FlatpakCachePlugin(CleanPlugin):
    """Removes unused Flatpak runtimes and extensions."""

    id = "flatpak_cache"
    name = "Flatpak Unused Runtimes"
    description = (
        "Removes Flatpak runtimes and extensions that are no longer used by "
        "any installed application."
    )
    category = "package_manager"
    icon = "application-x-addon-symbolic"
    risk_level = "moderate"
    item_noun = "runtime"

    @property
    def unavailable_reason(self) -> str | None:
        if not has_command("flatpak"):
            return "Flatpak not installed"
        return None

    def scan(self) -> ScanResult:
        entries: list[FileEntry] = []
        total = 0

        try:
            result = subprocess.run(
                ["flatpak", "uninstall", "--unused", "--no-interaction", "--dry-run"],
                capture_output=True,
                text=True,
            )
            # Parse output for unused refs
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and not line.startswith("Nothing") and "/" in line:
                    entries.append(
                        FileEntry(
                            path=Path(f"/var/lib/flatpak/runtime/{line}"),
                            size_bytes=0,  # Flatpak doesn't report sizes in dry-run
                            description=f"Unused runtime: {line}",
                            is_leaf=True,
                            file_count=1,
                        )
                    )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} unused Flatpak runtimes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        errors: list[str] = []

        try:
            result = subprocess.run(
                ["flatpak", "uninstall", "--unused", "--noninteractive", "-y"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append(f"flatpak uninstall failed: {result.stderr.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            errors.append(f"flatpak error: {e}")

        removed = len(entries) if not errors else 0
        return CleanResult(plugin_id=self.id, freed_bytes=0, errors=errors, files_removed=removed)
