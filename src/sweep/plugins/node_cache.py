"""Plugins to clean Node.js package manager cache directories."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup, SimpleCacheDirPlugin

_GROUP = PluginGroup("node", "Node.js Cache", "Package manager caches and tool data")


class NpmCachePlugin(MultiDirPlugin):
    """Cleans npm package cache."""

    @property
    def id(self) -> str:
        return "npm_cache"

    @property
    def name(self) -> str:
        return "npm"

    @property
    def description(self) -> str:
        return "npm package cache"

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "system-software-install-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".npm",)


class PnpmCachePlugin(MultiDirPlugin):
    """Cleans pnpm package cache."""

    @property
    def id(self) -> str:
        return "pnpm_cache"

    @property
    def name(self) -> str:
        return "pnpm"

    @property
    def description(self) -> str:
        return "pnpm package cache"

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "system-software-install-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        home = Path.home()
        return (
            home / ".local" / "share" / "pnpm" / "store",
            home / ".cache" / "pnpm",
        )


class YarnCachePlugin(MultiDirPlugin):
    """Cleans Yarn package cache."""

    @property
    def id(self) -> str:
        return "yarn_cache"

    @property
    def name(self) -> str:
        return "Yarn"

    @property
    def description(self) -> str:
        return "Yarn package cache"

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "system-software-install-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".cache" / "yarn",)


class BunCachePlugin(MultiDirPlugin):
    """Cleans Bun package cache."""

    @property
    def id(self) -> str:
        return "bun_cache"

    @property
    def name(self) -> str:
        return "Bun"

    @property
    def description(self) -> str:
        return "Bun package cache"

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "system-software-install-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".bun" / "install" / "cache",)


class TypescriptCachePlugin(SimpleCacheDirPlugin):
    """Cleans TypeScript cache."""

    @property
    def id(self) -> str:
        return "typescript_cache"

    @property
    def name(self) -> str:
        return "TypeScript"

    @property
    def description(self) -> str:
        return "TypeScript cache"

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "system-software-install-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "typescript"

    @property
    def _label(self) -> str:
        return "TypeScript"


class BiomeCachePlugin(SimpleCacheDirPlugin):
    """Cleans Biome cache."""

    @property
    def id(self) -> str:
        return "biome_cache"

    @property
    def name(self) -> str:
        return "Biome"

    @property
    def description(self) -> str:
        return "Biome cache"

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "system-software-install-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "biome"

    @property
    def _label(self) -> str:
        return "Biome"


class NodeGypCachePlugin(SimpleCacheDirPlugin):
    """Cleans node-gyp cache."""

    @property
    def id(self) -> str:
        return "node_gyp_cache"

    @property
    def name(self) -> str:
        return "node-gyp"

    @property
    def description(self) -> str:
        return "node-gyp cache"

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "system-software-install-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "node-gyp"

    @property
    def _label(self) -> str:
        return "node-gyp"
