"""Plugins to clean Node.js package manager cache directories."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup, SimpleCacheDirPlugin

_GROUP = PluginGroup("node", "Node.js Cache", "Package manager caches and tool data")


class NpmCachePlugin(MultiDirPlugin):
    """Cleans npm package cache."""

    id = "npm_cache"
    name = "npm"
    description = "npm package cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".npm",)


class PnpmCachePlugin(MultiDirPlugin):
    """Cleans pnpm package cache."""

    id = "pnpm_cache"
    name = "pnpm"
    description = "pnpm package cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (
            Path.home() / ".local" / "share" / "pnpm" / "store",
            Path.home() / ".cache" / "pnpm",
        )


class YarnCachePlugin(MultiDirPlugin):
    """Cleans Yarn package cache."""

    id = "yarn_cache"
    name = "Yarn"
    description = "Yarn package cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".cache" / "yarn",)


class BunCachePlugin(MultiDirPlugin):
    """Cleans Bun package cache."""

    id = "bun_cache"
    name = "Bun"
    description = "Bun package cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".bun" / "install" / "cache",)


class TypescriptCachePlugin(SimpleCacheDirPlugin):
    """Cleans TypeScript cache."""

    id = "typescript_cache"
    name = "TypeScript"
    description = "TypeScript cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP
    _cache_dir_name = "typescript"


class BiomeCachePlugin(SimpleCacheDirPlugin):
    """Cleans Biome cache."""

    id = "biome_cache"
    name = "Biome"
    description = "Biome cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP
    _cache_dir_name = "biome"


class NodeGypCachePlugin(SimpleCacheDirPlugin):
    """Cleans node-gyp cache."""

    id = "node_gyp_cache"
    name = "node-gyp"
    description = "node-gyp cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP
    _cache_dir_name = "node-gyp"
