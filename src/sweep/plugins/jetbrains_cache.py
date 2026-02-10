"""Plugin to clean JetBrains IDEs cache."""

from __future__ import annotations

from sweep.models.plugin import SimpleCacheDirPlugin


class JetBrainsCachePlugin(SimpleCacheDirPlugin):
    """Cleans the JetBrains IDEs cache (~/.cache/JetBrains).

    JetBrains products (IntelliJ IDEA, PyCharm, WebStorm, CLion,
    Android Studio, etc.) store caches here. These files are
    regenerated automatically when needed.
    """

    id = "jetbrains_cache"
    name = "JetBrains Cache"
    description = (
        "Removes cached files from JetBrains IDEs (IntelliJ, PyCharm, "
        "WebStorm, CLion). IDEs will regenerate caches as needed."
    )
    category = "development"
    icon = "text-editor-symbolic"
    _cache_dir_name = "JetBrains"
