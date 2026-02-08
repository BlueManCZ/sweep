"""Plugins to clean browser cache directories."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import PluginGroup, SimpleCacheDirPlugin

_GROUP = PluginGroup("browser", "Browser Cache", "Cached web pages, scripts, and media")


class FirefoxCachePlugin(SimpleCacheDirPlugin):
    """Cleans Firefox browser cache."""

    @property
    def id(self) -> str:
        return "firefox_cache"

    @property
    def name(self) -> str:
        return "Firefox"

    @property
    def description(self) -> str:
        return "Firefox HTTP cache"

    @property
    def category(self) -> str:
        return "browser"

    @property
    def icon(self) -> str:
        return "web-browser-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "mozilla/firefox"

    @property
    def _label(self) -> str:
        return "Firefox"


class ChromiumCachePlugin(SimpleCacheDirPlugin):
    """Cleans Chromium browser cache."""

    @property
    def id(self) -> str:
        return "chromium_cache"

    @property
    def name(self) -> str:
        return "Chromium"

    @property
    def description(self) -> str:
        return "Chromium HTTP cache"

    @property
    def category(self) -> str:
        return "browser"

    @property
    def icon(self) -> str:
        return "web-browser-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "chromium"

    @property
    def _label(self) -> str:
        return "Chromium"


class ChromeCachePlugin(SimpleCacheDirPlugin):
    """Cleans Google Chrome browser cache."""

    @property
    def id(self) -> str:
        return "chrome_cache"

    @property
    def name(self) -> str:
        return "Google Chrome"

    @property
    def description(self) -> str:
        return "Google Chrome HTTP cache"

    @property
    def category(self) -> str:
        return "browser"

    @property
    def icon(self) -> str:
        return "web-browser-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "google-chrome"

    @property
    def _label(self) -> str:
        return "Google Chrome"


class OperaCachePlugin(SimpleCacheDirPlugin):
    """Cleans Opera browser cache."""

    @property
    def id(self) -> str:
        return "opera_cache"

    @property
    def name(self) -> str:
        return "Opera"

    @property
    def description(self) -> str:
        return "Opera HTTP cache"

    @property
    def category(self) -> str:
        return "browser"

    @property
    def icon(self) -> str:
        return "web-browser-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "opera"

    @property
    def _label(self) -> str:
        return "Opera"


class ZenCachePlugin(SimpleCacheDirPlugin):
    """Cleans Zen browser cache."""

    @property
    def id(self) -> str:
        return "zen_cache"

    @property
    def name(self) -> str:
        return "Zen"

    @property
    def description(self) -> str:
        return "Zen HTTP cache"

    @property
    def category(self) -> str:
        return "browser"

    @property
    def icon(self) -> str:
        return "web-browser-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "zen"

    @property
    def _label(self) -> str:
        return "Zen"


class BraveCachePlugin(SimpleCacheDirPlugin):
    """Cleans Brave browser cache."""

    @property
    def id(self) -> str:
        return "brave_cache"

    @property
    def name(self) -> str:
        return "Brave"

    @property
    def description(self) -> str:
        return "Brave HTTP cache"

    @property
    def category(self) -> str:
        return "browser"

    @property
    def icon(self) -> str:
        return "web-browser-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "BraveSoftware/Brave-Browser"

    @property
    def _label(self) -> str:
        return "Brave"


class EdgeCachePlugin(SimpleCacheDirPlugin):
    """Cleans Microsoft Edge browser cache."""

    @property
    def id(self) -> str:
        return "edge_cache"

    @property
    def name(self) -> str:
        return "Microsoft Edge"

    @property
    def description(self) -> str:
        return "Microsoft Edge HTTP cache"

    @property
    def category(self) -> str:
        return "browser"

    @property
    def icon(self) -> str:
        return "web-browser-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "microsoft-edge"

    @property
    def _label(self) -> str:
        return "Microsoft Edge"


class EpiphanyCachePlugin(SimpleCacheDirPlugin):
    """Cleans Epiphany (GNOME Web) browser cache."""

    @property
    def id(self) -> str:
        return "epiphany_cache"

    @property
    def name(self) -> str:
        return "Epiphany"

    @property
    def description(self) -> str:
        return "Epiphany HTTP cache"

    @property
    def category(self) -> str:
        return "browser"

    @property
    def icon(self) -> str:
        return "web-browser-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "epiphany"

    @property
    def _label(self) -> str:
        return "Epiphany"
