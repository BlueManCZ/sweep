"""Plugins to clean JVM build tool cache directories."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup

_GROUP = PluginGroup("jvm", "JVM Dependencies", "Cached JVM build tool dependencies and artifacts")


class MavenCachePlugin(MultiDirPlugin):
    """Cleans Maven local repository."""

    @property
    def id(self) -> str:
        return "maven_cache"

    @property
    def name(self) -> str:
        return "Maven"

    @property
    def description(self) -> str:
        return "Maven local repository"

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "system-software-install-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".m2" / "repository",)


class GradleCachePlugin(MultiDirPlugin):
    """Cleans Gradle dependency and build cache."""

    @property
    def id(self) -> str:
        return "gradle_cache"

    @property
    def name(self) -> str:
        return "Gradle Cache"

    @property
    def description(self) -> str:
        return "Gradle dependency and build cache"

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "system-software-install-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".gradle" / "caches",)


class GradleWrapperCachePlugin(MultiDirPlugin):
    """Cleans downloaded Gradle distributions."""

    @property
    def id(self) -> str:
        return "gradle_wrapper_cache"

    @property
    def name(self) -> str:
        return "Gradle Wrapper"

    @property
    def description(self) -> str:
        return "Downloaded Gradle distributions"

    @property
    def category(self) -> str:
        return "development"

    @property
    def icon(self) -> str:
        return "system-software-install-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".gradle" / "wrapper",)
