"""Plugins to clean Rust toolchain cache directories."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup

_GROUP = PluginGroup("rust", "Cargo Registry", "Cargo registry index, crate sources, and build cache")


class CargoRegistryCachePlugin(MultiDirPlugin):
    """Cleans downloaded crate sources and index."""

    @property
    def id(self) -> str:
        return "cargo_registry_cache"

    @property
    def name(self) -> str:
        return "Cargo Registry"

    @property
    def description(self) -> str:
        return "Downloaded crate sources and index"

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
        return (Path.home() / ".cargo" / "registry",)


class CargoAdvisoryDbPlugin(MultiDirPlugin):
    """Cleans cargo-audit advisory database."""

    @property
    def id(self) -> str:
        return "cargo_advisory_db_cache"

    @property
    def name(self) -> str:
        return "Advisory DB"

    @property
    def description(self) -> str:
        return "cargo-audit advisory database"

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
        return (Path.home() / ".cargo" / "advisory-db",)
