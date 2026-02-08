"""Plugins to clean E2E testing framework caches."""

from __future__ import annotations

from sweep.models.plugin import PluginGroup, SimpleCacheDirPlugin

_GROUP = PluginGroup("e2e", "E2E Testing Browsers", "Bundled browsers used by testing frameworks")


class PlaywrightCachePlugin(SimpleCacheDirPlugin):
    """Cleans Playwright browser binaries."""

    @property
    def id(self) -> str:
        return "playwright_cache"

    @property
    def name(self) -> str:
        return "Playwright"

    @property
    def description(self) -> str:
        return "Playwright browser binaries"

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "preferences-system-symbolic"

    @property
    def item_noun(self) -> str:
        return "browser"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "ms-playwright"

    @property
    def _label(self) -> str:
        return "Playwright"


class CypressCachePlugin(SimpleCacheDirPlugin):
    """Cleans Cypress browser binaries."""

    @property
    def id(self) -> str:
        return "cypress_cache"

    @property
    def name(self) -> str:
        return "Cypress"

    @property
    def description(self) -> str:
        return "Cypress browser binaries"

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "preferences-system-symbolic"

    @property
    def item_noun(self) -> str:
        return "browser"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "Cypress"

    @property
    def _label(self) -> str:
        return "Cypress"
