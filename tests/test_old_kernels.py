"""Tests for old kernel image, module, and source cleanup plugins."""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from sweep.plugins.old_kernels import (
    OldKernelsPlugin,
    OldKernelModulesPlugin,
    OldKernelSourcesPlugin,
    _protected_versions,
    _boot_keep_versions,
    _modules_keep_versions,
    _sources_keep_names,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_kernel(boot: Path, version: str, age_offset: float = 0) -> None:
    """Create a full set of kernel files in a fake /boot."""
    for prefix in ("vmlinuz-", "System.map-", "config-"):
        f = boot / f"{prefix}{version}"
        f.write_bytes(b"k" * 1024)
    if age_offset:
        mtime = time.time() - age_offset
        for prefix in ("vmlinuz-", "System.map-", "config-"):
            os.utime(boot / f"{prefix}{version}", (mtime, mtime))


def _make_modules(modules: Path, version: str, size: int = 4096) -> None:
    """Create a fake /lib/modules/<version>/ directory."""
    d = modules / version
    d.mkdir(parents=True, exist_ok=True)
    (d / "modules.dep").write_bytes(b"m" * size)
    (d / "modules.alias").write_bytes(b"a" * (size // 2))


def _make_arch_modules(
    modules: Path,
    version: str,
    pkgbase_name: str,
    size: int = 4096,
) -> None:
    """Create a fake Arch-style /lib/modules/<version>/ with pkgbase."""
    _make_modules(modules, version, size)
    (modules / version / "pkgbase").write_text(f"{pkgbase_name}\n")


def _make_sources(usr_src: Path, version: str, size: int = 8192) -> Path:
    """Create a fake /usr/src/linux-<version>/ source tree."""
    d = usr_src / f"linux-{version}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "Makefile").write_bytes(b"M" * size)
    (d / ".config").write_bytes(b"C" * (size // 4))
    return d


# ---------------------------------------------------------------------------
# Gentoo-like system (vmlinuz-VERSION naming, no pkgbase)
# ---------------------------------------------------------------------------


class TestGentooSystem:
    """Simulates the user's Gentoo system with version-named kernels."""

    RUNNING = "6.12.58-gentoo-x86_64"

    @pytest.fixture
    def gentoo(self, tmp_path):
        boot = tmp_path / "boot"
        boot.mkdir()
        modules = tmp_path / "lib" / "modules"
        modules.mkdir(parents=True)

        # Non-kernel files that must survive
        grub = boot / "grub"
        grub.mkdir()
        (grub / "grub.cfg").write_text("menuentry {}")
        (boot / "amd-uc.img").write_bytes(b"u" * 512)
        (boot / ".keep").write_text("")

        # Kernels: newest → oldest
        _make_kernel(boot, "6.12.58-gentoo-x86_64", age_offset=0)
        _make_kernel(boot, "6.12.41-gentoo-x86_64", age_offset=100)
        _make_kernel(boot, "6.12.16-gentoo-x86_64", age_offset=200)
        _make_kernel(boot, "6.6.58-gentoo-r1-x86_64", age_offset=300)

        # Modules: current kernels + ancient orphans
        for ver in (
            "6.12.58-gentoo-x86_64",
            "6.12.41-gentoo-x86_64",
            "6.12.16-gentoo-x86_64",
            "6.6.58-gentoo-r1-x86_64",
            "6.1.67-gentoo-x86_64",
            "5.15.88-gentoo-x86_64",
        ):
            _make_modules(modules, ver)

        with (
            patch("sweep.plugins.old_kernels._BOOT_DIR", boot),
            patch("sweep.plugins.old_kernels._MODULES_DIR", modules),
            patch("platform.release", return_value=self.RUNNING),
        ):
            yield boot, modules

    def test_boot_keeps_running_and_one_previous(self, gentoo):
        keep = _boot_keep_versions()
        assert "6.12.58-gentoo-x86_64" in keep  # running
        assert "6.12.41-gentoo-x86_64" in keep  # most recent previous
        assert len(keep) == 2

    def test_boot_scan_deletes_old_kernels(self, gentoo):
        boot, _ = gentoo
        result = OldKernelsPlugin().scan()
        deleted_names = {e.path.name for e in result.entries}

        # Old kernels are marked for deletion
        assert "vmlinuz-6.12.16-gentoo-x86_64" in deleted_names
        assert "vmlinuz-6.6.58-gentoo-r1-x86_64" in deleted_names
        assert "System.map-6.12.16-gentoo-x86_64" in deleted_names
        assert "config-6.6.58-gentoo-r1-x86_64" in deleted_names

    def test_boot_scan_keeps_recent_kernels(self, gentoo):
        result = OldKernelsPlugin().scan()
        deleted_names = {e.path.name for e in result.entries}

        assert "vmlinuz-6.12.58-gentoo-x86_64" not in deleted_names
        assert "vmlinuz-6.12.41-gentoo-x86_64" not in deleted_names

    def test_boot_scan_never_touches_non_kernel_files(self, gentoo):
        boot, _ = gentoo
        result = OldKernelsPlugin().scan()
        deleted_paths = {e.path for e in result.entries}

        # grub, microcode, .keep must never appear in scan results
        assert boot / "grub" not in deleted_paths
        assert boot / "grub" / "grub.cfg" not in deleted_paths
        assert boot / "amd-uc.img" not in deleted_paths
        assert boot / ".keep" not in deleted_paths

    def test_boot_clean_preserves_non_kernel_files(self, gentoo):
        boot, _ = gentoo
        plugin = OldKernelsPlugin()
        entries = plugin.scan().entries
        plugin.clean(entries)

        # Non-kernel files still exist
        assert (boot / "grub" / "grub.cfg").exists()
        assert (boot / "amd-uc.img").exists()
        assert (boot / ".keep").exists()

        # Kept kernels still exist
        assert (boot / "vmlinuz-6.12.58-gentoo-x86_64").exists()
        assert (boot / "vmlinuz-6.12.41-gentoo-x86_64").exists()

        # Deleted kernels are gone
        assert not (boot / "vmlinuz-6.12.16-gentoo-x86_64").exists()
        assert not (boot / "vmlinuz-6.6.58-gentoo-r1-x86_64").exists()

    def test_modules_keeps_versions_with_boot_images(self, gentoo):
        keep = _modules_keep_versions()

        # Everything with a vmlinuz is kept
        assert "6.12.58-gentoo-x86_64" in keep
        assert "6.12.41-gentoo-x86_64" in keep
        assert "6.12.16-gentoo-x86_64" in keep
        assert "6.6.58-gentoo-r1-x86_64" in keep

    def test_modules_scan_deletes_orphans(self, gentoo):
        result = OldKernelModulesPlugin().scan()
        deleted = {e.path.name for e in result.entries}

        # Only truly orphaned modules (no vmlinuz in /boot)
        assert "6.1.67-gentoo-x86_64" in deleted
        assert "5.15.88-gentoo-x86_64" in deleted
        assert len(result.entries) == 2

    def test_modules_scan_keeps_all_installed_versions(self, gentoo):
        result = OldKernelModulesPlugin().scan()
        deleted = {e.path.name for e in result.entries}

        assert "6.12.58-gentoo-x86_64" not in deleted
        assert "6.12.41-gentoo-x86_64" not in deleted
        assert "6.12.16-gentoo-x86_64" not in deleted
        assert "6.6.58-gentoo-r1-x86_64" not in deleted


# ---------------------------------------------------------------------------
# Arch Linux system (vmlinuz-linux naming, pkgbase files)
# ---------------------------------------------------------------------------


class TestArchSystem:
    """Simulates Arch Linux with package-named kernels and pkgbase files."""

    RUNNING = "6.12.2-arch1-1"

    @pytest.fixture
    def arch(self, tmp_path):
        boot = tmp_path / "boot"
        boot.mkdir()
        modules = tmp_path / "lib" / "modules"
        modules.mkdir(parents=True)

        # Arch-style boot files (no version in filename)
        (boot / "vmlinuz-linux").write_bytes(b"k" * 2048)
        (boot / "vmlinuz-linux-lts").write_bytes(b"k" * 2048)
        (boot / "initramfs-linux.img").write_bytes(b"i" * 4096)
        (boot / "initramfs-linux-lts.img").write_bytes(b"i" * 4096)
        (boot / "initramfs-linux-fallback.img").write_bytes(b"i" * 8192)
        (boot / "grub").mkdir()
        (boot / "grub" / "grub.cfg").write_text("menuentry {}")
        (boot / "intel-ucode.img").write_bytes(b"u" * 512)

        # Installed kernel packages (with pkgbase)
        _make_arch_modules(modules, "6.12.2-arch1-1", "linux")
        _make_arch_modules(modules, "6.6.50-1-lts", "linux-lts")

        # Orphan: old version, package uninstalled (no pkgbase)
        _make_modules(modules, "6.11.8-arch1-1")

        with (
            patch("sweep.plugins.old_kernels._BOOT_DIR", boot),
            patch("sweep.plugins.old_kernels._MODULES_DIR", modules),
            patch("platform.release", return_value=self.RUNNING),
        ):
            yield boot, modules

    def test_protected_includes_pkgbase_names(self, arch):
        protected = _protected_versions()

        # uname -r
        assert "6.12.2-arch1-1" in protected
        # Module dir names (from pkgbase presence)
        assert "6.6.50-1-lts" in protected
        # pkgbase *contents* (map to vmlinuz filenames)
        assert "linux" in protected
        assert "linux-lts" in protected

    def test_boot_never_deletes_arch_kernels(self, arch):
        result = OldKernelsPlugin().scan()
        deleted_names = {e.path.name for e in result.entries}

        # vmlinuz-linux and vmlinuz-linux-lts must never be deleted
        assert "vmlinuz-linux" not in deleted_names
        assert "vmlinuz-linux-lts" not in deleted_names
        assert "initramfs-linux.img" not in deleted_names
        assert "initramfs-linux-lts.img" not in deleted_names
        assert "initramfs-linux-fallback.img" not in deleted_names

    def test_boot_never_touches_grub(self, arch):
        boot, _ = arch
        result = OldKernelsPlugin().scan()
        deleted_paths = {e.path for e in result.entries}

        assert boot / "grub" not in deleted_paths
        assert boot / "grub" / "grub.cfg" not in deleted_paths
        assert boot / "intel-ucode.img" not in deleted_paths

    def test_modules_keeps_installed_packages(self, arch):
        result = OldKernelModulesPlugin().scan()
        deleted = {e.path.name for e in result.entries}

        assert "6.12.2-arch1-1" not in deleted
        assert "6.6.50-1-lts" not in deleted

    def test_modules_deletes_orphan(self, arch):
        result = OldKernelModulesPlugin().scan()
        deleted = {e.path.name for e in result.entries}

        assert "6.11.8-arch1-1" in deleted
        assert len(result.entries) == 1


# ---------------------------------------------------------------------------
# Arch with three kernel flavors (linux + linux-lts + linux-zen)
# ---------------------------------------------------------------------------


class TestArchThreeKernels:
    """Arch system with more kernel flavors than _KEEP_LATEST."""

    RUNNING = "6.12.2-arch1-1"

    @pytest.fixture
    def arch3(self, tmp_path):
        boot = tmp_path / "boot"
        boot.mkdir()
        modules = tmp_path / "lib" / "modules"
        modules.mkdir(parents=True)

        (boot / "vmlinuz-linux").write_bytes(b"k" * 1024)
        (boot / "vmlinuz-linux-lts").write_bytes(b"k" * 1024)
        (boot / "vmlinuz-linux-zen").write_bytes(b"k" * 1024)

        _make_arch_modules(modules, "6.12.2-arch1-1", "linux")
        _make_arch_modules(modules, "6.6.50-1-lts", "linux-lts")
        _make_arch_modules(modules, "6.12.2.zen1-1", "linux-zen")

        with (
            patch("sweep.plugins.old_kernels._BOOT_DIR", boot),
            patch("sweep.plugins.old_kernels._MODULES_DIR", modules),
            patch("platform.release", return_value=self.RUNNING),
        ):
            yield boot, modules

    def test_all_three_kernels_protected(self, arch3):
        """All installed Arch packages are kept even when > _KEEP_LATEST."""
        result = OldKernelsPlugin().scan()
        assert len(result.entries) == 0

    def test_all_three_module_dirs_kept(self, arch3):
        result = OldKernelModulesPlugin().scan()
        assert len(result.entries) == 0


# ---------------------------------------------------------------------------
# /boot safety: non-kernel files must never be touched
# ---------------------------------------------------------------------------


class TestBootSafety:
    """Ensure non-kernel contents of /boot are never included in scan."""

    RUNNING = "6.1.0-current"

    @pytest.fixture
    def boot_with_extras(self, tmp_path):
        boot = tmp_path / "boot"
        boot.mkdir()
        modules = tmp_path / "lib" / "modules"
        modules.mkdir(parents=True)

        # Non-kernel contents that must survive
        (boot / "grub").mkdir()
        (boot / "grub" / "grub.cfg").write_text("menuentry {}")
        (boot / "grub" / "grubenv").write_bytes(b"e" * 128)
        (boot / "grub" / "fonts").mkdir()
        (boot / "grub" / "fonts" / "unicode.pf2").write_bytes(b"f" * 256)
        (boot / "EFI").mkdir()
        (boot / "EFI" / "BOOT").mkdir()
        (boot / "EFI" / "BOOT" / "BOOTX64.EFI").write_bytes(b"e" * 512)
        (boot / "loader").mkdir()
        (boot / "loader" / "loader.conf").write_text("default arch")
        (boot / "loader" / "entries").mkdir()
        (boot / "loader" / "entries" / "arch.conf").write_text("title Arch")
        (boot / "intel-ucode.img").write_bytes(b"u" * 1024)
        (boot / "amd-ucode.img").write_bytes(b"u" * 1024)
        (boot / ".keep").write_text("")
        (boot / "memtest86+.bin").write_bytes(b"t" * 512)

        # Kernels: 3 versions, keep 2
        _make_kernel(boot, "6.1.0-current", age_offset=0)
        _make_kernel(boot, "6.1.0-previous", age_offset=100)
        _make_kernel(boot, "5.15.0-old", age_offset=200)
        # Also add initramfs for the old one
        (boot / "initramfs-5.15.0-old.img").write_bytes(b"r" * 2048)

        _make_modules(modules, "6.1.0-current")

        with (
            patch("sweep.plugins.old_kernels._BOOT_DIR", boot),
            patch("sweep.plugins.old_kernels._MODULES_DIR", modules),
            patch("platform.release", return_value=self.RUNNING),
        ):
            yield boot

    def test_scan_only_matches_kernel_files(self, boot_with_extras):
        result = OldKernelsPlugin().scan()
        deleted_names = {e.path.name for e in result.entries}

        # Only the old kernel's files should appear
        assert deleted_names == {
            "vmlinuz-5.15.0-old",
            "System.map-5.15.0-old",
            "config-5.15.0-old",
            "initramfs-5.15.0-old.img",
        }

    def test_grub_dir_untouched(self, boot_with_extras):
        boot = boot_with_extras
        result = OldKernelsPlugin().scan()
        all_paths = {str(e.path) for e in result.entries}

        for grub_file in boot.joinpath("grub").rglob("*"):
            assert str(grub_file) not in all_paths

    def test_efi_dir_untouched(self, boot_with_extras):
        boot = boot_with_extras
        result = OldKernelsPlugin().scan()
        all_paths = {str(e.path) for e in result.entries}

        for efi_file in boot.joinpath("EFI").rglob("*"):
            assert str(efi_file) not in all_paths

    def test_bootloader_entries_untouched(self, boot_with_extras):
        boot = boot_with_extras
        result = OldKernelsPlugin().scan()
        all_paths = {str(e.path) for e in result.entries}

        for loader_file in boot.joinpath("loader").rglob("*"):
            assert str(loader_file) not in all_paths

    def test_microcode_untouched(self, boot_with_extras):
        boot = boot_with_extras
        result = OldKernelsPlugin().scan()
        deleted_names = {e.path.name for e in result.entries}

        assert "intel-ucode.img" not in deleted_names
        assert "amd-ucode.img" not in deleted_names

    def test_other_boot_files_untouched(self, boot_with_extras):
        boot = boot_with_extras
        result = OldKernelsPlugin().scan()
        deleted_names = {e.path.name for e in result.entries}

        assert ".keep" not in deleted_names
        assert "memtest86+.bin" not in deleted_names

    def test_clean_preserves_everything_except_old_kernel(self, boot_with_extras):
        boot = boot_with_extras
        plugin = OldKernelsPlugin()
        entries = plugin.scan().entries
        plugin.clean(entries)

        # All non-kernel items survive
        assert (boot / "grub" / "grub.cfg").exists()
        assert (boot / "grub" / "grubenv").exists()
        assert (boot / "grub" / "fonts" / "unicode.pf2").exists()
        assert (boot / "EFI" / "BOOT" / "BOOTX64.EFI").exists()
        assert (boot / "loader" / "loader.conf").exists()
        assert (boot / "loader" / "entries" / "arch.conf").exists()
        assert (boot / "intel-ucode.img").exists()
        assert (boot / "amd-ucode.img").exists()
        assert (boot / ".keep").exists()
        assert (boot / "memtest86+.bin").exists()

        # Kept kernels survive
        assert (boot / "vmlinuz-6.1.0-current").exists()
        assert (boot / "vmlinuz-6.1.0-previous").exists()

        # Old kernel is gone
        assert not (boot / "vmlinuz-5.15.0-old").exists()
        assert not (boot / "initramfs-5.15.0-old.img").exists()


# ---------------------------------------------------------------------------
# Plugin properties and edge cases
# ---------------------------------------------------------------------------


class TestPluginProperties:
    def test_boot_plugin_properties(self):
        p = OldKernelsPlugin()
        assert p.id == "old_kernels"
        assert p.category == "system"
        assert p.requires_root is True
        assert p.risk_level == "aggressive"
        assert p.group is not None
        assert p.group.id == "kernel"

    def test_modules_plugin_properties(self):
        p = OldKernelModulesPlugin()
        assert p.id == "old_kernel_modules"
        assert p.category == "system"
        assert p.requires_root is True
        assert p.risk_level == "aggressive"
        assert p.group is not None
        assert p.group.id == "kernel"

    def test_sources_plugin_properties(self):
        p = OldKernelSourcesPlugin()
        assert p.id == "old_kernel_sources"
        assert p.category == "system"
        assert p.requires_root is True
        assert p.risk_level == "aggressive"
        assert p.group is not None
        assert p.group.id == "kernel"

    def test_all_plugins_share_same_group(self):
        group = OldKernelsPlugin().group
        assert OldKernelModulesPlugin().group == group
        assert OldKernelSourcesPlugin().group == group


class TestUnavailable:
    def test_boot_unavailable_when_no_boot(self, tmp_path):
        with patch("sweep.plugins.old_kernels._BOOT_DIR", tmp_path / "noboot"):
            p = OldKernelsPlugin()
            assert p.unavailable_reason is not None
            assert not p.is_available()

    def test_modules_unavailable_when_no_modules(self, tmp_path):
        with patch("sweep.plugins.old_kernels._MODULES_DIR", tmp_path / "nomods"):
            p = OldKernelModulesPlugin()
            assert p.unavailable_reason is not None
            assert not p.is_available()

    def test_sources_unavailable_when_no_usr_src(self, tmp_path):
        with patch("sweep.plugins.old_kernels._SOURCES_DIR", tmp_path / "nosrc"):
            p = OldKernelSourcesPlugin()
            assert p.unavailable_reason is not None
            assert not p.is_available()


class TestEdgeCases:
    """Edge cases: single kernel, no old modules, etc."""

    RUNNING = "6.12.0-only"

    @pytest.fixture
    def single_kernel(self, tmp_path):
        boot = tmp_path / "boot"
        boot.mkdir()
        modules = tmp_path / "lib" / "modules"
        modules.mkdir(parents=True)

        _make_kernel(boot, "6.12.0-only")
        _make_modules(modules, "6.12.0-only")

        with (
            patch("sweep.plugins.old_kernels._BOOT_DIR", boot),
            patch("sweep.plugins.old_kernels._MODULES_DIR", modules),
            patch("platform.release", return_value=self.RUNNING),
        ):
            yield boot, modules

    def test_single_kernel_nothing_to_delete(self, single_kernel):
        assert OldKernelsPlugin().scan().entries == []
        assert OldKernelModulesPlugin().scan().entries == []

    def test_single_kernel_has_items_false(self, single_kernel):
        assert OldKernelsPlugin().has_items() is False

    @pytest.fixture
    def updated_not_rebooted(self, tmp_path):
        """Simulates a kernel update before reboot (Arch scenario)."""
        boot = tmp_path / "boot"
        boot.mkdir()
        modules = tmp_path / "lib" / "modules"
        modules.mkdir(parents=True)

        # New kernel installed, old one still running
        (boot / "vmlinuz-linux").write_bytes(b"k" * 1024)
        _make_arch_modules(modules, "6.13.0-arch1-1", "linux")
        # Old running kernel's modules might still exist
        _make_modules(modules, "6.12.2-arch1-1")

        running = "6.12.2-arch1-1"

        with (
            patch("sweep.plugins.old_kernels._BOOT_DIR", boot),
            patch("sweep.plugins.old_kernels._MODULES_DIR", modules),
            patch("platform.release", return_value=running),
        ):
            yield boot, modules

    def test_running_kernel_always_protected(self, updated_not_rebooted):
        """Even if the running kernel has no vmlinuz, its modules are safe."""
        result = OldKernelModulesPlugin().scan()
        deleted = {e.path.name for e in result.entries}

        assert "6.12.2-arch1-1" not in deleted  # running
        assert "6.13.0-arch1-1" not in deleted  # has pkgbase

    def test_boot_keeps_new_kernel_after_update(self, updated_not_rebooted):
        result = OldKernelsPlugin().scan()
        deleted_names = {e.path.name for e in result.entries}

        # vmlinuz-linux maps to "linux" in pkgbase → protected
        assert "vmlinuz-linux" not in deleted_names


# ---------------------------------------------------------------------------
# Old kernel sources (/usr/src)
# ---------------------------------------------------------------------------


class TestGentooSources:
    """Simulates the user's Gentoo /usr/src with orphaned source trees."""

    RUNNING = "6.12.58-gentoo-x86_64"

    @pytest.fixture
    def gentoo_src(self, tmp_path):
        boot = tmp_path / "boot"
        boot.mkdir()
        modules = tmp_path / "lib" / "modules"
        modules.mkdir(parents=True)
        usr_src = tmp_path / "usr" / "src"
        usr_src.mkdir(parents=True)

        # Only the current kernel in /boot
        _make_kernel(boot, "6.12.58-gentoo-x86_64")
        _make_modules(modules, "6.12.58-gentoo-x86_64")

        # Source trees: current + many old ones
        current = _make_sources(usr_src, "6.12.58-gentoo")
        _make_sources(usr_src, "6.12.41-gentoo")
        _make_sources(usr_src, "6.12.16-gentoo")
        _make_sources(usr_src, "6.6.58-gentoo-r1")
        _make_sources(usr_src, "6.6.47-gentoo")
        _make_sources(usr_src, "6.6.38-gentoo")

        # /usr/src/linux symlink → current sources
        (usr_src / "linux").symlink_to(current)

        # Non-kernel dirs that must survive
        (usr_src / "linux-firmware").mkdir()
        (usr_src / "linux-firmware" / "amd").write_bytes(b"f" * 512)
        (usr_src / "debug").mkdir()
        (usr_src / "debug" / "info").write_bytes(b"d" * 256)

        with (
            patch("sweep.plugins.old_kernels._BOOT_DIR", boot),
            patch("sweep.plugins.old_kernels._MODULES_DIR", modules),
            patch("sweep.plugins.old_kernels._SOURCES_DIR", usr_src),
            patch("platform.release", return_value=self.RUNNING),
        ):
            yield usr_src

    def test_keep_names_includes_current(self, gentoo_src):
        keep = _sources_keep_names()
        assert "linux-6.12.58-gentoo" in keep

    def test_keep_names_excludes_old(self, gentoo_src):
        keep = _sources_keep_names()
        assert "linux-6.6.38-gentoo" not in keep
        assert "linux-6.6.47-gentoo" not in keep

    def test_scan_removes_orphaned_sources(self, gentoo_src):
        result = OldKernelSourcesPlugin().scan()
        deleted = {e.path.name for e in result.entries}

        assert "linux-6.12.41-gentoo" in deleted
        assert "linux-6.12.16-gentoo" in deleted
        assert "linux-6.6.58-gentoo-r1" in deleted
        assert "linux-6.6.47-gentoo" in deleted
        assert "linux-6.6.38-gentoo" in deleted
        assert len(result.entries) == 5

    def test_scan_keeps_current_sources(self, gentoo_src):
        result = OldKernelSourcesPlugin().scan()
        deleted = {e.path.name for e in result.entries}

        assert "linux-6.12.58-gentoo" not in deleted

    def test_scan_never_touches_non_kernel_dirs(self, gentoo_src):
        result = OldKernelSourcesPlugin().scan()
        deleted = {e.path.name for e in result.entries}

        assert "linux-firmware" not in deleted
        assert "debug" not in deleted
        assert "linux" not in deleted  # symlink

    def test_scan_never_touches_symlink(self, gentoo_src):
        result = OldKernelSourcesPlugin().scan()
        deleted_paths = {e.path for e in result.entries}

        assert gentoo_src / "linux" not in deleted_paths

    def test_clean_removes_old_preserves_current(self, gentoo_src):
        plugin = OldKernelSourcesPlugin()
        entries = plugin.scan().entries
        plugin.clean(entries)

        # Current sources survive
        assert (gentoo_src / "linux-6.12.58-gentoo").exists()
        assert (gentoo_src / "linux-6.12.58-gentoo" / "Makefile").exists()

        # Old sources are gone
        assert not (gentoo_src / "linux-6.12.41-gentoo").exists()
        assert not (gentoo_src / "linux-6.6.38-gentoo").exists()

        # Non-kernel dirs survive
        assert (gentoo_src / "linux-firmware" / "amd").exists()
        assert (gentoo_src / "debug" / "info").exists()

    def test_has_items_true(self, gentoo_src):
        assert OldKernelSourcesPlugin().has_items() is True


class TestSourcesWithMultipleBootKernels:
    """Sources are kept when their version matches a boot image."""

    RUNNING = "6.12.58-gentoo-x86_64"

    @pytest.fixture
    def src_with_boot(self, tmp_path):
        boot = tmp_path / "boot"
        boot.mkdir()
        modules = tmp_path / "lib" / "modules"
        modules.mkdir(parents=True)
        usr_src = tmp_path / "usr" / "src"
        usr_src.mkdir(parents=True)

        # Two kernels in /boot
        _make_kernel(boot, "6.12.58-gentoo-x86_64")
        _make_kernel(boot, "6.12.41-gentoo-x86_64", age_offset=100)

        # Source dirs for both + one orphan
        current = _make_sources(usr_src, "6.12.58-gentoo")
        _make_sources(usr_src, "6.12.41-gentoo")
        _make_sources(usr_src, "6.6.38-gentoo")
        (usr_src / "linux").symlink_to(current)

        with (
            patch("sweep.plugins.old_kernels._BOOT_DIR", boot),
            patch("sweep.plugins.old_kernels._MODULES_DIR", modules),
            patch("sweep.plugins.old_kernels._SOURCES_DIR", usr_src),
            patch("platform.release", return_value=self.RUNNING),
        ):
            yield usr_src

    def test_keeps_sources_with_boot_images(self, src_with_boot):
        result = OldKernelSourcesPlugin().scan()
        deleted = {e.path.name for e in result.entries}

        # Both have matching vmlinuz in /boot
        assert "linux-6.12.58-gentoo" not in deleted
        assert "linux-6.12.41-gentoo" not in deleted

    def test_removes_orphan_only(self, src_with_boot):
        result = OldKernelSourcesPlugin().scan()
        deleted = {e.path.name for e in result.entries}

        assert deleted == {"linux-6.6.38-gentoo"}


class TestSourcesSingleKernel:
    """Nothing to remove when there's only one kernel source tree."""

    RUNNING = "6.12.58-gentoo-x86_64"

    @pytest.fixture
    def single_src(self, tmp_path):
        boot = tmp_path / "boot"
        boot.mkdir()
        modules = tmp_path / "lib" / "modules"
        modules.mkdir(parents=True)
        usr_src = tmp_path / "usr" / "src"
        usr_src.mkdir(parents=True)

        _make_kernel(boot, "6.12.58-gentoo-x86_64")
        current = _make_sources(usr_src, "6.12.58-gentoo")
        (usr_src / "linux").symlink_to(current)

        with (
            patch("sweep.plugins.old_kernels._BOOT_DIR", boot),
            patch("sweep.plugins.old_kernels._MODULES_DIR", modules),
            patch("sweep.plugins.old_kernels._SOURCES_DIR", usr_src),
            patch("platform.release", return_value=self.RUNNING),
        ):
            yield usr_src

    def test_nothing_to_delete(self, single_src):
        assert OldKernelSourcesPlugin().scan().entries == []

    def test_has_items_false(self, single_src):
        assert OldKernelSourcesPlugin().has_items() is False


class TestSourcesSymlinkProtection:
    """The /usr/src/linux symlink target is always protected."""

    RUNNING = "6.1.0-different"

    @pytest.fixture
    def symlink_mismatch(self, tmp_path):
        """Symlink points to sources that don't match the running kernel."""
        boot = tmp_path / "boot"
        boot.mkdir()
        modules = tmp_path / "lib" / "modules"
        modules.mkdir(parents=True)
        usr_src = tmp_path / "usr" / "src"
        usr_src.mkdir(parents=True)

        _make_kernel(boot, "6.1.0-different")
        # Symlink points to 6.12.58 but running kernel is 6.1.0
        target = _make_sources(usr_src, "6.12.58-gentoo")
        _make_sources(usr_src, "6.6.38-gentoo")
        (usr_src / "linux").symlink_to(target)

        with (
            patch("sweep.plugins.old_kernels._BOOT_DIR", boot),
            patch("sweep.plugins.old_kernels._MODULES_DIR", modules),
            patch("sweep.plugins.old_kernels._SOURCES_DIR", usr_src),
            patch("platform.release", return_value=self.RUNNING),
        ):
            yield usr_src

    def test_symlink_target_always_kept(self, symlink_mismatch):
        result = OldKernelSourcesPlugin().scan()
        deleted = {e.path.name for e in result.entries}

        # Symlink target is protected even though it doesn't match uname -r
        assert "linux-6.12.58-gentoo" not in deleted
        # Orphan is removed
        assert "linux-6.6.38-gentoo" in deleted
