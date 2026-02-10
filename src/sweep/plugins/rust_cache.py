"""Plugins to clean Rust toolchain cache directories."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup

_GROUP = PluginGroup("rust", "Cargo Registry", "Cargo registry index, crate sources, and build cache")


class CargoRegistryCachePlugin(MultiDirPlugin):
    """Cleans downloaded crate sources and index."""

    id = "cargo_registry_cache"
    name = "Cargo Registry"
    description = "Downloaded crate sources and index"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".cargo" / "registry",)


class CargoAdvisoryDbPlugin(MultiDirPlugin):
    """Cleans cargo-audit advisory database."""

    id = "cargo_advisory_db_cache"
    name = "Advisory DB"
    description = "cargo-audit advisory database"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".cargo" / "advisory-db",)
