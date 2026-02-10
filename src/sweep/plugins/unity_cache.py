"""Plugin to clean Unity3D cache."""

from __future__ import annotations

from sweep.models.plugin import SimpleCacheDirPlugin


class UnityCachePlugin(SimpleCacheDirPlugin):
    """Cleans the Unity3D engine cache."""

    id = "unity_cache"
    name = "Unity3D"
    description = "Unity game engine shader and asset cache"
    category = "development"
    icon = "applications-games-symbolic"
    _cache_dir_name = "unity3d"
