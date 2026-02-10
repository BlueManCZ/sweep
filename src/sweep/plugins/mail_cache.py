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

    id = "thunderbird_cache"
    name = "Thunderbird"
    description = "Thunderbird cache data"
    category = "mail"
    icon = "mail-unread-symbolic"
    group = _GROUP
    _cache_dir_name = "thunderbird"


class EvolutionCachePlugin(SimpleCacheDirPlugin):
    """Cleans Evolution mail client cache."""

    id = "evolution_cache"
    name = "Evolution"
    description = "Evolution cache data"
    category = "mail"
    icon = "mail-unread-symbolic"
    group = _GROUP
    _cache_dir_name = "evolution"


class GearyCachePlugin(SimpleCacheDirPlugin):
    """Cleans Geary mail client cache."""

    id = "geary_cache"
    name = "Geary"
    description = "Geary cache data"
    category = "mail"
    icon = "mail-unread-symbolic"
    group = _GROUP
    _cache_dir_name = "geary"


class MailspringCachePlugin(MultiDirPlugin):
    """Cleans Mailspring mail client cache directories."""

    id = "mailspring_cache"
    name = "Mailspring"
    description = "Mailspring cache data"
    category = "mail"
    icon = "mail-unread-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        config_dir = Path.home() / ".config" / "Mailspring"
        return tuple(config_dir / d for d in _MAILSPRING_CACHE_SUBDIRS)
