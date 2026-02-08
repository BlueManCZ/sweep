"""Plugins to clean Winetricks and Protontricks caches."""

from __future__ import annotations

from sweep.models.plugin import PluginGroup, SimpleCacheDirPlugin

_GROUP = PluginGroup("wine", "Wine Tools Cache", "Downloaded installers and runtime caches for Wine")


class WineCachePlugin(SimpleCacheDirPlugin):
    """Cleans Wine download cache."""

    @property
    def id(self) -> str:
        return "wine_cache"

    @property
    def name(self) -> str:
        return "Wine"

    @property
    def description(self) -> str:
        return "Wine download cache (Mono, Gecko installers)"

    @property
    def icon(self) -> str:
        return "applications-games-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "wine"

    @property
    def _label(self) -> str:
        return "Wine"


class WinetricksCachePlugin(SimpleCacheDirPlugin):
    """Cleans Winetricks download cache."""

    @property
    def id(self) -> str:
        return "winetricks_cache"

    @property
    def name(self) -> str:
        return "Winetricks"

    @property
    def description(self) -> str:
        return "Winetricks download cache"

    @property
    def icon(self) -> str:
        return "applications-games-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "winetricks"

    @property
    def _label(self) -> str:
        return "Winetricks"


class ProtontricksCachePlugin(SimpleCacheDirPlugin):
    """Cleans Protontricks download cache."""

    @property
    def id(self) -> str:
        return "protontricks_cache"

    @property
    def name(self) -> str:
        return "Protontricks"

    @property
    def description(self) -> str:
        return "Protontricks download cache"

    @property
    def icon(self) -> str:
        return "applications-games-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "protontricks"

    @property
    def _label(self) -> str:
        return "Protontricks"
