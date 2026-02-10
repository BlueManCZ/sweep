"""Plugins to clean browser cache directories."""

from __future__ import annotations

from sweep.models.plugin import PluginGroup, SimpleCacheDirPlugin

_GROUP = PluginGroup("browser", "Browser Cache", "Cached web pages, scripts, and media")


class FirefoxCachePlugin(SimpleCacheDirPlugin):
    """Cleans Firefox browser cache."""

    id = "firefox_cache"
    name = "Firefox"
    description = "Firefox HTTP cache"
    category = "browser"
    icon = "web-browser-symbolic"
    group = _GROUP
    _cache_dir_name = "mozilla/firefox"


class ChromiumCachePlugin(SimpleCacheDirPlugin):
    """Cleans Chromium browser cache."""

    id = "chromium_cache"
    name = "Chromium"
    description = "Chromium HTTP cache"
    category = "browser"
    icon = "web-browser-symbolic"
    group = _GROUP
    _cache_dir_name = "chromium"


class ChromeCachePlugin(SimpleCacheDirPlugin):
    """Cleans Google Chrome browser cache."""

    id = "chrome_cache"
    name = "Google Chrome"
    description = "Google Chrome HTTP cache"
    category = "browser"
    icon = "web-browser-symbolic"
    group = _GROUP
    _cache_dir_name = "google-chrome"


class OperaCachePlugin(SimpleCacheDirPlugin):
    """Cleans Opera browser cache."""

    id = "opera_cache"
    name = "Opera"
    description = "Opera HTTP cache"
    category = "browser"
    icon = "web-browser-symbolic"
    group = _GROUP
    _cache_dir_name = "opera"


class ZenCachePlugin(SimpleCacheDirPlugin):
    """Cleans Zen browser cache."""

    id = "zen_cache"
    name = "Zen"
    description = "Zen HTTP cache"
    category = "browser"
    icon = "web-browser-symbolic"
    group = _GROUP
    _cache_dir_name = "zen"


class BraveCachePlugin(SimpleCacheDirPlugin):
    """Cleans Brave browser cache."""

    id = "brave_cache"
    name = "Brave"
    description = "Brave HTTP cache"
    category = "browser"
    icon = "web-browser-symbolic"
    group = _GROUP
    _cache_dir_name = "BraveSoftware/Brave-Browser"


class EdgeCachePlugin(SimpleCacheDirPlugin):
    """Cleans Microsoft Edge browser cache."""

    id = "edge_cache"
    name = "Microsoft Edge"
    description = "Microsoft Edge HTTP cache"
    category = "browser"
    icon = "web-browser-symbolic"
    group = _GROUP
    _cache_dir_name = "microsoft-edge"


class EpiphanyCachePlugin(SimpleCacheDirPlugin):
    """Cleans Epiphany (GNOME Web) browser cache."""

    id = "epiphany_cache"
    name = "Epiphany"
    description = "Epiphany HTTP cache"
    category = "browser"
    icon = "web-browser-symbolic"
    group = _GROUP
    _cache_dir_name = "epiphany"
