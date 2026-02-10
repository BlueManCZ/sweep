"""Plugin to clean GitHub Copilot cache."""

from __future__ import annotations

from sweep.models.plugin import SimpleCacheDirPlugin


class CopilotCachePlugin(SimpleCacheDirPlugin):
    """Cleans the GitHub Copilot cache (~/.cache/github-copilot).

    GitHub Copilot caches project context and index data for code
    completions. These files are rebuilt automatically as you work.
    """

    id = "copilot_cache"
    name = "GitHub Copilot Cache"
    description = (
        "Removes cached project indexes and context data from GitHub "
        "Copilot. Indexes will be rebuilt automatically as you work."
    )
    category = "development"
    icon = "github-symbolic"
    _cache_dir_name = "github-copilot"
