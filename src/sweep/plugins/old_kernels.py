"""Plugin to clean old kernel images."""

from __future__ import annotations

import logging
import platform
from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.utils import remove_entries

log = logging.getLogger(__name__)

_BOOT_DIR = Path("/boot")


class OldKernelsPlugin(CleanPlugin):
    """Removes old kernel images, keeping current and one previous."""

    @property
    def id(self) -> str:
        return "old_kernels"

    @property
    def name(self) -> str:
        return "Old Kernel Images"

    @property
    def description(self) -> str:
        return (
            "Removes old Linux kernel images from /boot, keeping the current "
            "running kernel and one previous version."
        )

    @property
    def category(self) -> str:
        return "system"

    @property
    def icon(self) -> str:
        return "computer-symbolic"

    @property
    def requires_root(self) -> bool:
        return True

    @property
    def risk_level(self) -> str:
        return "aggressive"

    @property
    def unavailable_reason(self) -> str | None:
        if not _BOOT_DIR.is_dir():
            return "/boot directory not found"
        return None

    def has_items(self) -> bool:
        try:
            return len(list(_BOOT_DIR.glob("vmlinuz-*"))) > 2
        except OSError:
            return False

    def scan(self) -> ScanResult:
        current_kernel = platform.release()
        entries: list[FileEntry] = []
        total = 0

        # Find vmlinuz files
        kernel_files = sorted(
            [f for f in _BOOT_DIR.glob("vmlinuz-*") if f.is_file()],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        # Keep current + 1 most recent
        keep_versions: set[str] = {current_kernel}
        for kf in kernel_files:
            version = kf.name.removeprefix("vmlinuz-")
            if version != current_kernel:
                keep_versions.add(version)
                break  # keep only one previous

        for kf in kernel_files:
            version = kf.name.removeprefix("vmlinuz-")
            if version in keep_versions:
                continue

            # Collect all related files for this kernel version
            related_patterns = [
                f"vmlinuz-{version}",
                f"initramfs-{version}*",
                f"initrd.img-{version}",
                f"System.map-{version}",
                f"config-{version}",
            ]
            for pattern in related_patterns:
                for path in _BOOT_DIR.glob(pattern):
                    try:
                        size = path.stat().st_size
                        entries.append(FileEntry(
                            path=path,
                            size_bytes=size,
                            description=f"Old kernel: {path.name}",
                            file_count=1,
                        ))
                        total += size
                    except OSError:
                        pass

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} old kernel files totaling {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        freed, removed, errors = remove_entries(entries)
        return CleanResult(plugin_id=self.id, freed_bytes=freed, errors=errors, files_removed=removed)
