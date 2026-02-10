"""Plugin to clean Strawberry Music Player cache."""

from __future__ import annotations

from sweep.models.plugin import SimpleCacheDirPlugin


class StrawberryCachePlugin(SimpleCacheDirPlugin):
    """Cleans the Strawberry Music Player cache (~/.cache/strawberry).

    Strawberry caches album art, network responses, and pixmaps.
    These files are regenerated automatically when needed.
    """

    id = "strawberry_cache"
    name = "Strawberry Cache"
    description = (
        "Removes cached album art and network data from the Strawberry "
        "Music Player. Caches will be rebuilt as you browse your library."
    )
    icon = "media-playback-start-symbolic"
    _cache_dir_name = "strawberry"
