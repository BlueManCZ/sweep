"""Plugins to clean old kernel images, modules, and sources."""

from __future__ import annotations

import logging
import platform
from pathlib import Path

from sweep.models.plugin import CleanPlugin, PluginGroup
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.utils import dir_info, remove_entries

log = logging.getLogger(__name__)

_BOOT_DIR = Path("/boot")
_MODULES_DIR = Path("/lib/modules")
_SOURCES_DIR = Path("/usr/src")

_GROUP = PluginGroup("kernel", "Linux Kernel", "Old kernel images, modules, and sources")


# Number of recent kernels to keep in /boot (including the running one).
_KEEP_LATEST = 2


def _protected_versions() -> set[str]:
    """Versions that must NEVER be removed regardless of age.

    - The currently running kernel (``uname -r``).
    - Any version with a ``pkgbase`` file in /lib/modules/ (Arch, etc.)
      — its presence means the kernel package is still installed.
      The pkgbase *contents* (e.g. ``linux``, ``linux-lts``) are also
      added so that ``vmlinuz-linux`` is recognised as protected even
      though the extracted "version" doesn't match ``uname -r``.
    """
    protected: set[str] = {platform.release()}
    if _MODULES_DIR.is_dir():
        for mod_dir in _MODULES_DIR.iterdir():
            pkgbase = mod_dir / "pkgbase"
            if mod_dir.is_dir() and pkgbase.is_file():
                protected.add(mod_dir.name)
                try:
                    protected.add(pkgbase.read_text().strip())
                except OSError:
                    pass
    return protected


def _boot_keep_versions() -> set[str]:
    """Versions to keep in /boot.

    Keeps all protected versions plus enough recent kernels to
    reach ``_KEEP_LATEST`` total.  Protected versions that happen
    to be in /boot count toward the limit.
    """
    protected = _protected_versions()
    keep: set[str] = set(protected)

    kernel_files = sorted(
        [f for f in _BOOT_DIR.glob("vmlinuz-*") if f.is_file()],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    for kf in kernel_files:
        if len(keep) >= _KEEP_LATEST:
            break
        keep.add(kf.name.removeprefix("vmlinuz-"))

    return keep


def _modules_keep_versions() -> set[str]:
    """Versions to keep in /lib/modules.

    Keeps all protected versions plus any version that still has a
    kernel image in /boot (i.e. the boot plugin decided to keep it).
    """
    keep = _protected_versions()
    if _BOOT_DIR.is_dir():
        for f in _BOOT_DIR.glob("vmlinuz-*"):
            if f.is_file():
                keep.add(f.name.removeprefix("vmlinuz-"))
    return keep


def _is_kernel_source_dir(path: Path) -> bool:
    """Check if a path is a kernel source directory (linux-<version>).

    Matches ``linux-6.12.58-gentoo`` but not ``linux-firmware`` or
    ``linux-headers-6.12.58``.
    """
    if not path.is_dir() or not path.name.startswith("linux-"):
        return False
    version = path.name.removeprefix("linux-")
    return bool(version) and version[0].isdigit()


def _sources_keep_names() -> set[str]:
    """Source directory names in /usr/src to keep.

    Keeps sources matching any protected version (running kernel,
    pkgbase entries) or any version with a boot image, plus the
    ``/usr/src/linux`` symlink target.

    Uses prefix matching to handle the architecture suffix difference:
    source dir ``linux-6.12.58-gentoo`` matches running kernel
    ``6.12.58-gentoo-x86_64``.
    """
    protected = _protected_versions()
    if _BOOT_DIR.is_dir():
        for f in _BOOT_DIR.glob("vmlinuz-*"):
            if f.is_file():
                protected.add(f.name.removeprefix("vmlinuz-"))

    keep: set[str] = set()

    # Always keep the /usr/src/linux symlink target
    linux_symlink = _SOURCES_DIR / "linux"
    if linux_symlink.is_symlink():
        try:
            keep.add(linux_symlink.resolve().name)
        except OSError:
            pass

    # Keep sources whose version prefix-matches any protected version
    try:
        for src_dir in _SOURCES_DIR.iterdir():
            if not _is_kernel_source_dir(src_dir):
                continue
            src_version = src_dir.name.removeprefix("linux-")
            for pv in protected:
                if pv == src_version or pv.startswith(src_version + "-"):
                    keep.add(src_dir.name)
                    break
    except OSError:
        pass

    return keep


class OldKernelsPlugin(CleanPlugin):
    """Removes old kernel images, keeping current and one previous."""

    id = "old_kernels"
    name = "Old Kernel Images"
    description = "Removes old Linux kernel images from /boot, keeping the running kernel and one previous version."
    category = "system"
    icon = "computer-symbolic"
    group = _GROUP
    requires_root = True
    risk_level = "aggressive"

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
        keep = _boot_keep_versions()
        entries: list[FileEntry] = []
        total = 0

        kernel_files = sorted(
            [f for f in _BOOT_DIR.glob("vmlinuz-*") if f.is_file()],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        for kf in kernel_files:
            version = kf.name.removeprefix("vmlinuz-")
            if version in keep:
                continue

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
                        entries.append(
                            FileEntry(
                                path=path,
                                size_bytes=size,
                                description=f"Old kernel: {version}",
                                is_leaf=True,
                                file_count=1,
                            )
                        )
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


class OldKernelModulesPlugin(CleanPlugin):
    """Removes /lib/modules directories for old kernels."""

    id = "old_kernel_modules"
    name = "Old Kernel Modules"
    description = "Removes /lib/modules directories for kernel versions that no longer have a kernel image in /boot."
    category = "system"
    icon = "computer-symbolic"
    group = _GROUP
    requires_root = True
    risk_level = "aggressive"

    @property
    def unavailable_reason(self) -> str | None:
        if not _MODULES_DIR.is_dir():
            return "/lib/modules directory not found"
        return None

    def has_items(self) -> bool:
        try:
            keep = _modules_keep_versions()
            return any(d.name not in keep for d in _MODULES_DIR.iterdir() if d.is_dir())
        except OSError:
            return False

    def scan(self) -> ScanResult:
        keep = _modules_keep_versions()
        entries: list[FileEntry] = []
        total = 0

        try:
            for mod_dir in sorted(_MODULES_DIR.iterdir()):
                if not mod_dir.is_dir() or mod_dir.name in keep:
                    continue
                try:
                    size, fcount = dir_info(mod_dir)
                    entries.append(
                        FileEntry(
                            path=mod_dir,
                            size_bytes=size,
                            description=f"Old kernel modules: {mod_dir.name}",
                            is_leaf=True,
                            file_count=fcount,
                        )
                    )
                    total += size
                except OSError:
                    log.debug("Cannot access: %s", mod_dir)
        except OSError:
            log.debug("Cannot read %s", _MODULES_DIR)

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} old module directories totaling {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        freed, removed, errors = remove_entries(entries, count_files=True)
        return CleanResult(plugin_id=self.id, freed_bytes=freed, errors=errors, files_removed=removed)


class OldKernelSourcesPlugin(CleanPlugin):
    """Removes old kernel source trees from /usr/src.

    On Gentoo (and similar source-based distros), unmerging a
    ``gentoo-sources`` package does not remove the source directory
    if it contains build artifacts.  This plugin detects orphaned
    source trees and offers to remove them.
    """

    id = "old_kernel_sources"
    name = "Old Kernel Sources"
    description = "Removes old kernel source trees from /usr/src that no longer match any installed or running kernel."
    category = "system"
    icon = "computer-symbolic"
    group = _GROUP
    requires_root = True
    risk_level = "aggressive"

    @property
    def unavailable_reason(self) -> str | None:
        if not _SOURCES_DIR.is_dir():
            return "/usr/src directory not found"
        return None

    def has_items(self) -> bool:
        try:
            keep = _sources_keep_names()
            return any(_is_kernel_source_dir(d) and d.name not in keep for d in _SOURCES_DIR.iterdir())
        except OSError:
            return False

    def scan(self) -> ScanResult:
        keep = _sources_keep_names()
        entries: list[FileEntry] = []
        total = 0

        try:
            for src_dir in sorted(_SOURCES_DIR.iterdir()):
                if not _is_kernel_source_dir(src_dir):
                    continue
                if src_dir.name in keep:
                    continue
                try:
                    size, fcount = dir_info(src_dir)
                    entries.append(
                        FileEntry(
                            path=src_dir,
                            size_bytes=size,
                            description=f"Old kernel sources: {src_dir.name}",
                            is_leaf=True,
                            file_count=fcount,
                        )
                    )
                    total += size
                except OSError:
                    log.debug("Cannot access: %s", src_dir)
        except OSError:
            log.debug("Cannot read %s", _SOURCES_DIR)

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} old kernel source trees totaling {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        freed, removed, errors = remove_entries(entries, count_files=True)
        return CleanResult(plugin_id=self.id, freed_bytes=freed, errors=errors, files_removed=removed)
