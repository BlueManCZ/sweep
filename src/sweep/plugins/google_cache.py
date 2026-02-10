"""Plugins to clean Google application caches."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup, SimpleCacheDirPlugin

_GROUP = PluginGroup("google", "Google Cache", "Cached data from Google applications")


class GoogleXdgCachePlugin(SimpleCacheDirPlugin):
    """Cleans Google XDG cache (~/.cache/Google)."""

    id = "google_xdg_cache"
    name = "Google XDG Cache"
    description = "Google app cache under ~/.cache/Google"
    icon = "system-run-symbolic"
    group = _GROUP
    _cache_dir_name = "Google"


class GoogleEarthCachePlugin(MultiDirPlugin):
    """Cleans Google Earth Pro imagery and tile cache."""

    id = "google_earth_cache"
    name = "Google Earth Cache"
    description = "Google Earth Pro imagery and tile cache"
    category = "application"
    icon = "system-run-symbolic"
    group = _GROUP
    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".googleearth" / "Cache",)
