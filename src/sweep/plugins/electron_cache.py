"""Plugins to clean Electron ecosystem caches."""

from __future__ import annotations

from sweep.models.plugin import PluginGroup, SimpleCacheDirPlugin

_GROUP = PluginGroup("electron", "Electron Cache", "Chromium engine caches from Electron apps")


class ElectronCachePlugin(SimpleCacheDirPlugin):
    """Cleans Electron framework cache (GPU shaders, code caches, binaries)."""

    id = "electron_cache"
    name = "Electron"
    description = "Electron framework cache"
    icon = "utilities-terminal-symbolic"
    group = _GROUP
    _cache_dir_name = "electron"


class ElectronBuilderCachePlugin(SimpleCacheDirPlugin):
    """Cleans Electron Builder packaging cache."""

    id = "electron_builder_cache"
    name = "Electron Builder"
    description = "Electron Builder packaging cache"
    icon = "utilities-terminal-symbolic"
    group = _GROUP
    _cache_dir_name = "electron-builder"
