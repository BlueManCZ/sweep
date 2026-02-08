"""Plugins to clean Google application caches."""

from __future__ import annotations

import logging
from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup, SimpleCacheDirPlugin

log = logging.getLogger(__name__)

_GROUP = PluginGroup("google", "Google Cache", "Cached data from Google applications")


class GoogleXdgCachePlugin(SimpleCacheDirPlugin):
    """Cleans Google XDG cache (~/.cache/Google)."""

    @property
    def id(self) -> str:
        return "google_xdg_cache"

    @property
    def name(self) -> str:
        return "Google XDG Cache"

    @property
    def description(self) -> str:
        return "Google app cache under ~/.cache/Google"

    @property
    def icon(self) -> str:
        return "system-run-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "Google"

    @property
    def _label(self) -> str:
        return "Google XDG Cache"


class GoogleEarthCachePlugin(MultiDirPlugin):
    """Cleans Google Earth Pro imagery and tile cache."""

    @property
    def id(self) -> str:
        return "google_earth_cache"

    @property
    def name(self) -> str:
        return "Google Earth Cache"

    @property
    def description(self) -> str:
        return "Google Earth Pro imagery and tile cache"

    @property
    def category(self) -> str:
        return "application"

    @property
    def icon(self) -> str:
        return "system-run-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".googleearth" / "Cache",)
