"""Plugin to clean GitHub Copilot cache."""

from __future__ import annotations

from sweep.models.plugin import SimpleCacheDirPlugin


class CopilotCachePlugin(SimpleCacheDirPlugin):
    """Cleans the GitHub Copilot cache (~/.cache/github-copilot).

    GitHub Copilot caches project context and index data for code
    completions. These files are rebuilt automatically as you work.
    """

    @property
    def id(self) -> str:
        return "copilot_cache"

    @property
    def name(self) -> str:
        return "GitHub Copilot Cache"

    @property
    def description(self) -> str:
        return (
            "Removes cached project indexes and context data from GitHub "
            "Copilot. Indexes will be rebuilt automatically as you work."
        )

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "github-symbolic"

    @property
    def _cache_dir_name(self) -> str:
        return "github-copilot"
