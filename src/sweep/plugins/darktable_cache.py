"""Plugin to clean Darktable photo editor cache."""

from __future__ import annotations

from sweep.models.plugin import SimpleCacheDirPlugin


class DarktableCachePlugin(SimpleCacheDirPlugin):
    """Cleans the Darktable image editor cache (~/.cache/darktable).

    Darktable stores thumbnail mipmaps and other generated image data
    here. These files are regenerated automatically when needed.
    """

    @property
    def id(self) -> str:
        return "darktable_cache"

    @property
    def name(self) -> str:
        return "Darktable Cache"

    @property
    def description(self) -> str:
        return (
            "Removes cached thumbnail mipmaps and generated image data "
            "from the Darktable photo editor. Darktable will regenerate "
            "these files as needed."
        )

    @property
    def icon(self) -> str:
        return "camera-photo-symbolic"

    @property
    def _cache_dir_name(self) -> str:
        return "darktable"
