"""Plugins to clean E2E testing framework caches."""

from __future__ import annotations

from sweep.models.plugin import PluginGroup, SimpleCacheDirPlugin

_GROUP = PluginGroup("e2e", "E2E Testing Browsers", "Bundled browsers used by testing frameworks")


class PlaywrightCachePlugin(SimpleCacheDirPlugin):
    """Cleans Playwright browser binaries."""

    id = "playwright_cache"
    name = "Playwright"
    description = "Playwright browser binaries"
    category = "development"
    icon = "preferences-system-symbolic"
    item_noun = "browser"
    group = _GROUP
    _cache_dir_name = "ms-playwright"


class CypressCachePlugin(SimpleCacheDirPlugin):
    """Cleans Cypress browser binaries."""

    id = "cypress_cache"
    name = "Cypress"
    description = "Cypress browser binaries"
    category = "development"
    icon = "preferences-system-symbolic"
    item_noun = "browser"
    group = _GROUP
    _cache_dir_name = "Cypress"
