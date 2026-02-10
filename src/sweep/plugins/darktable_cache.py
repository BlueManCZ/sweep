"""Plugin to clean Darktable photo editor cache."""

from __future__ import annotations

from sweep.models.plugin import SimpleCacheDirPlugin


class DarktableCachePlugin(SimpleCacheDirPlugin):
    """Cleans the Darktable image editor cache (~/.cache/darktable).

    Darktable stores thumbnail mipmaps and other generated image data
    here. These files are regenerated automatically when needed.
    """

    id = "darktable_cache"
    name = "Darktable Cache"
    description = (
        "Removes cached thumbnail mipmaps and generated image data "
        "from the Darktable photo editor. Darktable will regenerate "
        "these files as needed."
    )
    icon = "camera-photo-symbolic"
    _cache_dir_name = "darktable"
