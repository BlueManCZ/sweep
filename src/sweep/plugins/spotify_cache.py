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

    id = "spotify_cache"
    name = "Spotify Cache"
    description = (
        "Removes cached audio, album art, and browser data from "
        "Spotify. Offline downloads will need to be re-downloaded."
    )
    icon = "audio-x-generic-symbolic"
    risk_level = "moderate"
    _cache_dir_name = "spotify"
