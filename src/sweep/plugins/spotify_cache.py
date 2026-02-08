"""Plugin to clean Spotify desktop client cache."""

from __future__ import annotations

from sweep.models.plugin import SimpleCacheDirPlugin


class SpotifyCachePlugin(SimpleCacheDirPlugin):
    """Cleans the Spotify desktop client cache (~/.cache/spotify).

    Spotify caches album art, audio streams, browser data, and shader
    caches from its embedded Chromium engine. These files are regenerated
    automatically when Spotify runs again. Offline downloads will need
    to be re-downloaded.
    """

    @property
    def id(self) -> str:
        return "spotify_cache"

    @property
    def name(self) -> str:
        return "Spotify Cache"

    @property
    def description(self) -> str:
        return (
            "Removes cached audio, album art, and browser data from "
            "Spotify. Offline downloads will need to be re-downloaded."
        )

    @property
    def icon(self) -> str:
        return "audio-x-generic-symbolic"

    @property
    def _cache_dir_name(self) -> str:
        return "spotify"

    @property
    def risk_level(self) -> str:
        return "moderate"
