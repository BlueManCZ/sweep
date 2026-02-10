"""Plugins to clean Bitwig Studio cache and temporary data."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup

_GROUP = PluginGroup("bitwig", "Bitwig Studio", "Audio previews, logs, and temp projects")


def _bitwig_dir() -> Path:
    return Path.home() / ".BitwigStudio"


class BitwigCachePlugin(MultiDirPlugin):
    """Cleans Bitwig Studio audio previews, plugin caches, and downloads."""

    id = "bitwig_cache"
    name = "Bitwig Cache"
    description = "Audio previews, plugin caches, and downloads"
    category = "application"
    icon = "audio-x-generic-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (_bitwig_dir() / "cache",)


class BitwigLogsCachePlugin(MultiDirPlugin):
    """Cleans Bitwig Studio log files."""

    id = "bitwig_logs_cache"
    name = "Bitwig Logs"
    description = "Application log files"
    category = "application"
    icon = "audio-x-generic-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (_bitwig_dir() / "log",)


class BitwigTempProjectsCachePlugin(MultiDirPlugin):
    """Cleans Bitwig Studio temporary project data."""

    id = "bitwig_temp_projects_cache"
    name = "Bitwig Temp Projects"
    description = "Temporary project data"
    category = "application"
    icon = "audio-x-generic-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (_bitwig_dir() / "temp-projects",)
