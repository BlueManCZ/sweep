"""Plugins to clean mail client cache directories."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup, SimpleCacheDirPlugin

_GROUP = PluginGroup("mail", "Mail Client Cache", "Cached messages and attachments from mail clients")

_MAILSPRING_CACHE_SUBDIRS = [
    "Cache",
    "Code Cache",
    "GPUCache",
    "blob_storage",
    "compile-cache",
    "Crashpad",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "Shared Dictionary",
]


class ThunderbirdCachePlugin(SimpleCacheDirPlugin):
    """Cleans Thunderbird mail client cache."""

    @property
    def id(self) -> str:
        return "thunderbird_cache"

    @property
    def name(self) -> str:
        return "Thunderbird"

    @property
    def description(self) -> str:
        return "Thunderbird cache data"

    @property
    def category(self) -> str:
        return "mail"

    @property
    def icon(self) -> str:
        return "mail-unread-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "thunderbird"

    @property
    def _label(self) -> str:
        return "Thunderbird"


class EvolutionCachePlugin(SimpleCacheDirPlugin):
    """Cleans Evolution mail client cache."""

    @property
    def id(self) -> str:
        return "evolution_cache"

    @property
    def name(self) -> str:
        return "Evolution"

    @property
    def description(self) -> str:
        return "Evolution cache data"

    @property
    def category(self) -> str:
        return "mail"

    @property
    def icon(self) -> str:
        return "mail-unread-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "evolution"

    @property
    def _label(self) -> str:
        return "Evolution"


class GearyCachePlugin(SimpleCacheDirPlugin):
    """Cleans Geary mail client cache."""

    @property
    def id(self) -> str:
        return "geary_cache"

    @property
    def name(self) -> str:
        return "Geary"

    @property
    def description(self) -> str:
        return "Geary cache data"

    @property
    def category(self) -> str:
        return "mail"

    @property
    def icon(self) -> str:
        return "mail-unread-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "geary"

    @property
    def _label(self) -> str:
        return "Geary"


class MailspringCachePlugin(MultiDirPlugin):
    """Cleans Mailspring mail client cache directories."""

    @property
    def id(self) -> str:
        return "mailspring_cache"

    @property
    def name(self) -> str:
        return "Mailspring"

    @property
    def description(self) -> str:
        return "Mailspring cache data"

    @property
    def category(self) -> str:
        return "mail"

    @property
    def icon(self) -> str:
        return "mail-unread-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        config_dir = Path.home() / ".config" / "Mailspring"
        return tuple(config_dir / d for d in _MAILSPRING_CACHE_SUBDIRS)
