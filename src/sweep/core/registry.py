"""Central plugin registry."""

from __future__ import annotations

import logging
from typing import Iterator

from sweep.models.plugin import CleanPlugin, PluginGroup

log = logging.getLogger(__name__)


class PluginRegistry:
    """Stores and retrieves registered cleaning plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, CleanPlugin] = {}

    def register(self, plugin: CleanPlugin) -> None:
        """Register a plugin instance."""
        if plugin.id in self._plugins:
            log.warning("Plugin '%s' already registered, skipping duplicate", plugin.id)
            return
        self._plugins[plugin.id] = plugin
        log.debug("Registered plugin: %s (%s)", plugin.id, plugin.name)

    def get(self, plugin_id: str) -> CleanPlugin | None:
        """Get a plugin by its ID."""
        return self._plugins.get(plugin_id)

    def get_all(self) -> list[CleanPlugin]:
        """Get all registered plugins."""
        return list(self._plugins.values())

    def get_by_category(self, category: str) -> list[CleanPlugin]:
        """Get all plugins in a given category."""
        return [p for p in self._plugins.values() if p.category == category]

    def get_available(self) -> list[CleanPlugin]:
        """Get all plugins that are available on this system."""
        available = []
        for plugin in self._plugins.values():
            try:
                if plugin.is_available():
                    available.append(plugin)
            except Exception:
                log.exception("Error checking availability for plugin '%s'", plugin.id)
        return available

    def __len__(self) -> int:
        return len(self._plugins)

    def __iter__(self) -> Iterator[CleanPlugin]:
        return iter(self._plugins.values())

    def __contains__(self, plugin_id: str) -> bool:
        return plugin_id in self._plugins

    def get_groups(self) -> dict[str, list[CleanPlugin]]:
        """Group plugins by their PluginGroup id.

        Returns a dict mapping group_id -> list of plugins in that group.
        Only includes plugins that have a group set.
        """
        groups: dict[str, list[CleanPlugin]] = {}
        for plugin in self._plugins.values():
            if plugin.group is not None:
                groups.setdefault(plugin.group.id, []).append(plugin)
        return groups

    def get_group_plugins(self, group_id: str) -> list[CleanPlugin]:
        """Get all plugins belonging to a specific group."""
        return [p for p in self._plugins.values() if p.group is not None and p.group.id == group_id]
