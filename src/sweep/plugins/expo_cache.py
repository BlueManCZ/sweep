"""Plugins to clean Expo (React Native) cache directories."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup

_GROUP = PluginGroup("expo", "Expo Cache", "Mobile build artifacts and downloaded SDKs")


def _expo_dir() -> Path:
    return Path.home() / ".expo"


class ExpoApkCachePlugin(MultiDirPlugin):
    """Cleans cached Expo Go and Android APK downloads."""

    id = "expo_apk_cache"
    name = "Expo APKs"
    description = "Cached Expo Go and Android APK downloads"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        d = _expo_dir()
        return (d / "expo-go", d / "android-apk-cache")


class ExpoMetadataCachePlugin(MultiDirPlugin):
    """Cleans Expo schema, version, and module caches."""

    id = "expo_metadata_cache"
    name = "Expo Metadata"
    description = "Schema, version, and module caches"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        d = _expo_dir()
        return (d / "schema-cache", d / "versions-cache", d / "native-modules-cache")
