"""Plugin to clean WhatsApp for Linux cache."""

from __future__ import annotations

from sweep.models.plugin import SimpleCacheDirPlugin


class WhatsAppCachePlugin(SimpleCacheDirPlugin):
    """Cleans WhatsApp for Linux application cache."""

    id = "whatsapp_cache"
    name = "WhatsApp for Linux"
    description = "WhatsApp for Linux application cache"
    icon = "user-available-symbolic"
    _cache_dir_name = "whatsapp-for-linux"
    _label = "WhatsApp"
