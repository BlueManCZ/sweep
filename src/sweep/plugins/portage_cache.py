"""Plugins to clean Gentoo Portage distfiles, binary packages, and orphaned packages.

Uses gentoolkit's eclean Python API for distfiles/packages and
portage's ``calc_depclean`` for finding orphaned installed packages.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from sweep.models.clean_result import CleanResult
from sweep.models.plugin import CleanPlugin, PluginGroup
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.utils import dir_info

log = logging.getLogger(__name__)

_GROUP = PluginGroup("portage", "Portage", "Source tarballs, binary packages, and orphaned installs")
_VDB_PATH = Path("/var/db/pkg")


def _portage_available() -> bool:
    """Check if this is a Gentoo system with portage installed."""
    if not _VDB_PATH.is_dir():
        return False
    try:
        import portage  # noqa: F401

        return True
    except Exception:
        return False


def _gentoolkit_available() -> bool:
    """Check if gentoolkit's eclean API is available."""
    try:
        from gentoolkit.eclean.search import DistfilesSearch  # noqa: F401

        return True
    except Exception:
        return False


def _file_size(path: str) -> int:
    """Get file size, ignoring hard links (same as eclean)."""
    try:
        st = os.stat(path)
        return st.st_size if st.st_nlink == 1 else 0
    except OSError:
        return 0


def _get_installed_size(cpv: str) -> int:
    """Get the installed size of a package from the Portage VDB."""
    size_file = _VDB_PATH / cpv / "SIZE"
    try:
        return int(size_file.read_text().strip())
    except (OSError, ValueError):
        return 0


def _calc_depclean_candidates() -> list[str]:
    """Compute depclean candidates using portage's dependency resolver."""
    import portage
    from _emerge.RootConfig import RootConfig
    from _emerge.actions import calc_depclean
    from portage._sets import load_default_config
    from portage._sets.base import InternalPackageSet

    settings = portage.settings
    trees = portage.create_trees()
    eroot = settings["EROOT"]

    setconfig = load_default_config(settings, trees[eroot])
    root_config = RootConfig(settings, trees[eroot], setconfig)
    trees[eroot]["root_config"] = root_config

    myopts: dict[str, object] = {
        "--pretend": True,
        "--quiet": True,
        "--depclean-lib-check": "n",
    }
    args_set = InternalPackageSet(allow_repo=True)

    old_fd = os.dup(1)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    try:
        rval, cleanlist, _ordered, _req_pkg_count = calc_depclean(
            settings,
            trees,
            {},
            myopts,
            "depclean",
            args_set,
            spinner=None,
        )
    finally:
        os.dup2(old_fd, 1)
        os.close(old_fd)
        os.close(devnull)

    if rval != 0:
        raise RuntimeError(f"calc_depclean returned exit code {rval}")

    return [str(pkg.cpv) for pkg in cleanlist]


class PortageDistfilesPlugin(CleanPlugin):
    """Cleans obsolete Portage source distfiles."""

    id = "portage_distfiles"
    name = "Source Distfiles"
    description = "Obsolete source archives from /var/cache/distfiles"
    category = "package_manager"
    icon = "system-software-install-symbolic"
    requires_root = True
    risk_level = "moderate"
    item_noun = "file"
    group = _GROUP

    @property
    def unavailable_reason(self) -> str | None:
        if not _portage_available():
            return "Portage not installed"
        if not _gentoolkit_available():
            return "gentoolkit not installed"
        return None

    def scan(self) -> ScanResult:
        from gentoolkit.eclean.search import DistfilesSearch

        entries: list[FileEntry] = []
        total = 0

        searcher = DistfilesSearch(output=lambda msg: None)
        clean_me, _saved, _deprecated, vcs = searcher.findDistfiles(
            destructive=True,
        )

        for display_name, files in clean_me.items():
            for filepath in files:
                size = _file_size(filepath)
                entries.append(
                    FileEntry(
                        path=Path(filepath),
                        size_bytes=size,
                        description=f"Distfile: {display_name}",
                        is_leaf=True,
                        file_count=1,
                    )
                )
                total += size

        for checkout in vcs:
            checkout_path = Path(checkout)
            size, fcount = dir_info(checkout_path)
            entries.append(
                FileEntry(
                    path=checkout_path,
                    size_bytes=size,
                    description=f"VCS checkout: {checkout_path.name}",
                    is_leaf=True,
                    file_count=fcount,
                )
            )
            total += size

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} obsolete distfiles totaling {total} bytes",
        )


class PortagePackagesPlugin(CleanPlugin):
    """Cleans obsolete Portage binary packages."""

    id = "portage_packages"
    name = "Binary Packages"
    description = "Obsolete binary packages from /var/cache/binpkgs"
    category = "package_manager"
    icon = "system-software-install-symbolic"
    requires_root = True
    risk_level = "moderate"
    item_noun = "file"
    group = _GROUP

    @property
    def unavailable_reason(self) -> str | None:
        if not _portage_available():
            return "Portage not installed"
        if not _gentoolkit_available():
            return "gentoolkit not installed"
        return None

    def scan(self) -> ScanResult:
        from gentoolkit.eclean.search import findPackages, pkgdir

        entries: list[FileEntry] = []
        total = 0

        options = {
            "unique-use": False,
            "changed-deps": False,
            "ignore-failure": False,
        }

        dead_binpkgs, invalid_paths = findPackages(
            options,
            destructive=True,
            pkgdir=pkgdir,
        )

        for cpv, filepaths in dead_binpkgs.items():
            for filepath in filepaths:
                size = _file_size(filepath)
                entries.append(
                    FileEntry(
                        path=Path(filepath),
                        size_bytes=size,
                        description=f"Binary package: {cpv}",
                        is_leaf=True,
                        file_count=1,
                    )
                )
                total += size

        for cpv, filepaths in invalid_paths.items():
            for filepath in filepaths:
                size = _file_size(filepath)
                entries.append(
                    FileEntry(
                        path=Path(filepath),
                        size_bytes=size,
                        description=f"Invalid package: {cpv}",
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
            summary=f"Found {len(entries)} obsolete binary packages totaling {total} bytes",
        )


class PortageDepcleanPlugin(CleanPlugin):
    """Cleans orphaned installed packages no longer needed as dependencies."""

    id = "portage_depclean"
    name = "Orphaned Packages"
    description = "Packages no longer needed as dependencies"
    category = "package_manager"
    icon = "system-software-install-symbolic"
    requires_root = True
    risk_level = "moderate"
    item_noun = "package"
    group = _GROUP

    @property
    def unavailable_reason(self) -> str | None:
        if not _portage_available():
            return "Portage not installed"
        return None

    def scan(self) -> ScanResult:
        cpvs = _calc_depclean_candidates()

        entries: list[FileEntry] = []
        total = 0
        for cpv in cpvs:
            size = _get_installed_size(cpv)
            entries.append(
                FileEntry(
                    path=_VDB_PATH / cpv,
                    size_bytes=size,
                    description=cpv,
                    is_leaf=True,
                )
            )
            total += size

        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=entries,
            total_bytes=total,
            summary=f"Found {len(entries)} orphaned packages totaling {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        atoms: list[str] = []
        for entry in entries:
            try:
                cpv = entry.path.relative_to(_VDB_PATH)
                atoms.append(f"={cpv}")
            except ValueError:
                log.warning("Unexpected entry path for depclean: %s", entry.path)

        if not atoms:
            return CleanResult(plugin_id=self.id)

        result = subprocess.run(
            ["emerge", "--depclean", "--quiet", "--"] + atoms,
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode == 0:
            freed = sum(e.size_bytes for e in entries)
            return CleanResult(
                plugin_id=self.id,
                freed_bytes=freed,
                files_removed=len(entries),
            )

        error_msg = result.stderr.strip() or f"emerge returned exit code {result.returncode}"
        return CleanResult(
            plugin_id=self.id,
            errors=[f"emerge --depclean failed: {error_msg}"],
        )
