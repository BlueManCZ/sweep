"""Plugins to clean JVM build tool cache directories."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup

_GROUP = PluginGroup("jvm", "JVM Dependencies", "Cached JVM build tool dependencies and artifacts")


class MavenCachePlugin(MultiDirPlugin):
    """Cleans Maven local repository."""

    id = "maven_cache"
    name = "Maven"
    description = "Maven local repository"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".m2" / "repository",)


class GradleCachePlugin(MultiDirPlugin):
    """Cleans Gradle dependency and build cache."""

    id = "gradle_cache"
    name = "Gradle Cache"
    description = "Gradle dependency and build cache"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".gradle" / "caches",)


class GradleWrapperCachePlugin(MultiDirPlugin):
    """Cleans downloaded Gradle distributions."""

    id = "gradle_wrapper_cache"
    name = "Gradle Wrapper"
    description = "Downloaded Gradle distributions"
    category = "development"
    icon = "system-software-install-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".gradle" / "wrapper",)
