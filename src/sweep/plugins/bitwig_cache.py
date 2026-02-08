"""Plugins to clean Bitwig Studio cache and temporary data."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup

_GROUP = PluginGroup("bitwig", "Bitwig Studio", "Audio previews, logs, and temp projects")


class BitwigCachePlugin(MultiDirPlugin):
    """Cleans Bitwig Studio audio previews, plugin caches, and downloads."""

    @property
    def id(self) -> str:
        return "bitwig_cache"

    @property
    def name(self) -> str:
        return "Bitwig Cache"

    @property
    def description(self) -> str:
        return "Audio previews, plugin caches, and downloads"

    @property
    def category(self) -> str:
        return "application"

    @property
    def icon(self) -> str:
        return "audio-x-generic-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".BitwigStudio" / "cache",)


class BitwigLogsCachePlugin(MultiDirPlugin):
    """Cleans Bitwig Studio log files."""

    @property
    def id(self) -> str:
        return "bitwig_logs_cache"

    @property
    def name(self) -> str:
        return "Bitwig Logs"

    @property
    def description(self) -> str:
        return "Application log files"

    @property
    def category(self) -> str:
        return "application"

    @property
    def icon(self) -> str:
        return "audio-x-generic-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".BitwigStudio" / "log",)


class BitwigTempProjectsCachePlugin(MultiDirPlugin):
    """Cleans Bitwig Studio temporary project data."""

    @property
    def id(self) -> str:
        return "bitwig_temp_projects_cache"

    @property
    def name(self) -> str:
        return "Bitwig Temp Projects"

    @property
    def description(self) -> str:
        return "Temporary project data"

    @property
    def category(self) -> str:
        return "application"

    @property
    def icon(self) -> str:
        return "audio-x-generic-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".BitwigStudio" / "temp-projects",)
