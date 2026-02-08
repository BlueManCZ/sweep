"""Plugin to clean WhatsApp for Linux cache."""

from __future__ import annotations

from sweep.models.plugin import SimpleCacheDirPlugin


class WhatsAppCachePlugin(SimpleCacheDirPlugin):
    """Cleans WhatsApp for Linux application cache."""

    @property
    def id(self) -> str:
        return "whatsapp_cache"

    @property
    def name(self) -> str:
        return "WhatsApp for Linux"

    @property
    def description(self) -> str:
        return "WhatsApp for Linux application cache"

    @property
    def icon(self) -> str:
        return "user-available-symbolic"

    @property
    def _cache_dir_name(self) -> str:
        return "whatsapp-for-linux"

    @property
    def _label(self) -> str:
        return "WhatsApp"
