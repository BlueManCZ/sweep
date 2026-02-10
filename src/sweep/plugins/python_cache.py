"""Plugins to clean Python-related caches and stale package directories."""

from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path

from sweep.models.clean_result import CleanResult
from sweep.models.plugin import CleanPlugin, MultiDirPlugin, PluginGroup, SimpleCacheDirPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.utils import dir_info, remove_entries, xdg_cache_home

log = logging.getLogger(__name__)

_GROUP = PluginGroup("python", "Python Tools", "Package manager caches and virtual environment data")
_PYTHON_DIR_RE = re.compile(r"^python(\d+\.\d+)$")


class PipCachePlugin(SimpleCacheDirPlugin):
    """Cleans pip package cache."""

    id = "pip_cache"
    name = "pip"
    description = "pip package cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP
    _cache_dir_name = "pip"


class PipenvCachePlugin(SimpleCacheDirPlugin):
    """Cleans pipenv package cache."""

    id = "pipenv_cache"
    name = "pipenv"
    description = "pipenv package cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP
    _cache_dir_name = "pipenv"


class UvCachePlugin(SimpleCacheDirPlugin):
    """Cleans uv package cache."""

    id = "uv_cache"
    name = "uv"
    description = "uv package cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP
    _cache_dir_name = "uv"


class PoetryCachePlugin(SimpleCacheDirPlugin):
    """Cleans Poetry package cache."""

    id = "poetry_cache"
    name = "Poetry"
    description = "Poetry package cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP
    _cache_dir_name = "pypoetry"


class VirtualenvCachePlugin(SimpleCacheDirPlugin):
    """Cleans virtualenv package cache."""

    id = "virtualenv_cache"
    name = "virtualenv"
    description = "virtualenv package cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP
    _cache_dir_name = "virtualenv"


class BlackCachePlugin(SimpleCacheDirPlugin):
    """Cleans Black formatter cache."""

    id = "black_cache"
    name = "Black"
    description = "Black formatter cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP
    _cache_dir_name = "black"


class PylintCachePlugin(SimpleCacheDirPlugin):
    """Cleans Pylint cache."""

    id = "pylint_cache"
    name = "Pylint"
    description = "Pylint cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP
    _cache_dir_name = "pylint"


class VpythonCachePlugin(MultiDirPlugin):
    """Cleans Chromium depot_tools vpython virtual environment cache."""

    id = "vpython_cache"
    name = "vpython"
    description = "Chromium depot_tools vpython virtual environment cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        cache = xdg_cache_home()
        return (cache / ".vpython-root", cache / f"vpython-root.{os.getuid()}")


class PythonStalePkgsPlugin(CleanPlugin):
    """Cleans packages installed for Python versions no longer present."""

    id = "python_stale_packages"
    name = "Stale packages"
    description = "Packages installed for Python versions no longer present"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP

    def _local_lib(self) -> Path:
        return Path.home() / ".local" / "lib"

    def _find_stale_python_dirs(self) -> list[tuple[Path, str]]:
        """Find pythonX.Y dirs whose interpreter is missing."""
        lib_dir = self._local_lib()
        if not lib_dir.is_dir():
            return []

        stale: list[tuple[Path, str]] = []
        for entry in sorted(lib_dir.iterdir()):
            match = _PYTHON_DIR_RE.match(entry.name)
            if match and entry.is_dir():
                version = match.group(1)
                if not shutil.which(f"python{version}"):
                    stale.append((entry, version))
        return stale

    @property
    def unavailable_reason(self) -> str | None:
        if not self._find_stale_python_dirs():
            return "No stale Python directories found"
        return None

    def has_items(self) -> bool:
        return bool(self._find_stale_python_dirs())

    def scan(self) -> ScanResult:
        entries: list[FileEntry] = []
        total = 0

        for python_dir, version in self._find_stale_python_dirs():
            size, fcount = dir_info(python_dir)
            if size > 0:
                entries.append(
                    FileEntry(
                        path=python_dir,
                        size_bytes=size,
                        description=f"Packages for removed Python {version}",
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
            summary=f"Found {self.name}: {total} bytes",
        )

    def _do_clean(self, entries: list[FileEntry]) -> CleanResult:
        freed, removed, errors = remove_entries(
            entries,
            count_files=True,
            recreate_dirs=False,
        )
        return CleanResult(plugin_id=self.id, freed_bytes=freed, files_removed=removed, errors=errors)
