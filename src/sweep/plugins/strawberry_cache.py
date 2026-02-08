"""Plugin to clean Strawberry Music Player cache."""

from __future__ import annotations

from sweep.models.plugin import SimpleCacheDirPlugin


class StrawberryCachePlugin(SimpleCacheDirPlugin):
    """Cleans the Strawberry Music Player cache (~/.cache/strawberry).

    Strawberry caches album art, network responses, and pixmaps.
    These files are regenerated automatically when needed.
    """

    @property
    def id(self) -> str:
        return "strawberry_cache"

    @property
    def name(self) -> str:
        return "Strawberry Cache"

    @property
    def description(self) -> str:
        return (
            "Removes cached album art and network data from the Strawberry "
            "Music Player. Caches will be rebuilt as you browse your library."
        )

    @property
    def icon(self) -> str:
        return "media-playback-start-symbolic"

    @property
    def _cache_dir_name(self) -> str:
        return "strawberry"
