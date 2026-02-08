"""Plugin to clean Unity3D cache."""

from __future__ import annotations

from sweep.models.plugin import SimpleCacheDirPlugin


class UnityCachePlugin(SimpleCacheDirPlugin):
    """Cleans the Unity3D engine cache."""

    @property
    def id(self) -> str:
        return "unity_cache"

    @property
    def name(self) -> str:
        return "Unity3D"

    @property
    def description(self) -> str:
        return "Unity game engine shader and asset cache"

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "applications-games-symbolic"

    @property
    def _cache_dir_name(self) -> str:
        return "unity3d"

    @property
    def _label(self) -> str:
        return "Unity3D"
