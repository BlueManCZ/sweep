"""Plugin to clean JetBrains IDEs cache."""

from __future__ import annotations

from sweep.models.plugin import SimpleCacheDirPlugin


class JetBrainsCachePlugin(SimpleCacheDirPlugin):
    """Cleans the JetBrains IDEs cache (~/.cache/JetBrains).

    JetBrains products (IntelliJ IDEA, PyCharm, WebStorm, CLion,
    Android Studio, etc.) store caches here. These files are
    regenerated automatically when needed.
    """

    @property
    def id(self) -> str:
        return "jetbrains_cache"

    @property
    def name(self) -> str:
        return "JetBrains Cache"

    @property
    def description(self) -> str:
        return (
            "Removes cached files from JetBrains IDEs (IntelliJ, PyCharm, "
            "WebStorm, CLion). IDEs will regenerate caches as needed."
        )

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "text-editor-symbolic"

    @property
    def _cache_dir_name(self) -> str:
        return "JetBrains"
