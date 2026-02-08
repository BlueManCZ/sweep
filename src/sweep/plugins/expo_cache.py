"""Plugins to clean Expo (React Native) cache directories."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup

_GROUP = PluginGroup("expo", "Expo Cache", "Mobile build artifacts and downloaded SDKs")


class ExpoApkCachePlugin(MultiDirPlugin):
    """Cleans cached Expo Go and Android APK downloads."""

    @property
    def id(self) -> str:
        return "expo_apk_cache"

    @property
    def name(self) -> str:
        return "Expo APKs"

    @property
    def description(self) -> str:
        return "Cached Expo Go and Android APK downloads"

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
        expo = Path.home() / ".expo"
        return (expo / "expo-go", expo / "android-apk-cache")


class ExpoMetadataCachePlugin(MultiDirPlugin):
    """Cleans Expo schema, version, and module caches."""

    @property
    def id(self) -> str:
        return "expo_metadata_cache"

    @property
    def name(self) -> str:
        return "Expo Metadata"

    @property
    def description(self) -> str:
        return "Schema, version, and module caches"

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
        expo = Path.home() / ".expo"
        return (
            expo / "schema-cache",
            expo / "versions-cache",
            expo / "native-modules-cache",
        )
