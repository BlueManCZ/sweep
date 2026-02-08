"""Plugins to clean Electron ecosystem caches."""

from __future__ import annotations

from sweep.models.plugin import PluginGroup, SimpleCacheDirPlugin

_GROUP = PluginGroup("electron", "Electron Cache", "Chromium engine caches from Electron apps")


class ElectronCachePlugin(SimpleCacheDirPlugin):
    """Cleans Electron framework cache (GPU shaders, code caches, binaries)."""

    @property
    def id(self) -> str:
        return "electron_cache"

    @property
    def name(self) -> str:
        return "Electron"

    @property
    def description(self) -> str:
        return "Electron framework cache"

    @property
    def icon(self) -> str:
        return "utilities-terminal-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "electron"

    @property
    def _label(self) -> str:
        return "Electron"


class ElectronBuilderCachePlugin(SimpleCacheDirPlugin):
    """Cleans Electron Builder packaging cache."""

    @property
    def id(self) -> str:
        return "electron_builder_cache"

    @property
    def name(self) -> str:
        return "Electron Builder"

    @property
    def description(self) -> str:
        return "Electron Builder packaging cache"

    @property
    def icon(self) -> str:
        return "utilities-terminal-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "electron-builder"

    @property
    def _label(self) -> str:
        return "Electron Builder"
