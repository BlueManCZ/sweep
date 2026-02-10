"""Plugins to clean Winetricks and Protontricks caches."""

from __future__ import annotations

from sweep.models.plugin import PluginGroup, SimpleCacheDirPlugin

_GROUP = PluginGroup("wine", "Wine Tools Cache", "Downloaded installers and runtime caches for Wine")


class WineCachePlugin(SimpleCacheDirPlugin):
    """Cleans Wine download cache."""

    id = "wine_cache"
    name = "Wine"
    description = "Wine download cache (Mono, Gecko installers)"
    icon = "applications-games-symbolic"
    group = _GROUP
    _cache_dir_name = "wine"


class WinetricksCachePlugin(SimpleCacheDirPlugin):
    """Cleans Winetricks download cache."""

    id = "winetricks_cache"
    name = "Winetricks"
    description = "Winetricks download cache"
    icon = "applications-games-symbolic"
    group = _GROUP
    _cache_dir_name = "winetricks"


class ProtontricksCachePlugin(SimpleCacheDirPlugin):
    """Cleans Protontricks download cache."""

    id = "protontricks_cache"
    name = "Protontricks"
    description = "Protontricks download cache"
    icon = "applications-games-symbolic"
    group = _GROUP
    _cache_dir_name = "protontricks"
