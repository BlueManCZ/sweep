"""D-Bus service for GUI communication.

D-Bus methods use PascalCase per D-Bus convention, and type signatures
like "as" and "(ss)" are D-Bus protocol types, not Python syntax.
"""

from __future__ import annotations

import asyncio
import json
import logging

from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method, signal
from dbus_next import BusType

from sweep.core.engine import SweepEngine
from sweep.core.plugin_loader import load_plugins
from sweep.core.registry import PluginRegistry
from sweep.core.tracker import Tracker
from sweep.core.privileges import is_root
from sweep.storage import load_history

log = logging.getLogger(__name__)

_BUS_NAME = "io.github.BlueManCZ.sweep"
_OBJECT_PATH = "/io/github/BlueManCZ/sweep"
_INTERFACE = "io.github.BlueManCZ.sweep.Manager"


# noinspection PyPep8Naming,DuplicatedCode
class SweepDBusService(ServiceInterface):
    """D-Bus service interface for Sweep."""

    def __init__(self) -> None:
        super().__init__(_INTERFACE)
        self._registry = PluginRegistry()
        load_plugins(self._registry)
        self._engine = SweepEngine(self._registry)
        self._tracker = Tracker()

    @method()
    def ListPlugins(self) -> "s":  # type: ignore[override]
        """List all available plugins as JSON."""
        plugins = self._registry.get_available()
        data = [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "requires_root": p.requires_root,
                "risk_level": p.risk_level,
                "available": p.is_available(),
            }
            for p in plugins
        ]
        return json.dumps(data)

    @method()
    def Scan(self, plugin_ids: "as") -> "s":  # type: ignore[override]
        """Scan specified plugins, returning results as JSON."""
        ids = list(plugin_ids) if plugin_ids else None

        def progress(plugin_id: str, status: str) -> None:
            self.ScanProgress(plugin_id, status)

        results = self._engine.scan(plugin_ids=ids, on_progress=progress)
        data = [
            {
                "plugin_id": r.plugin_id,
                "plugin_name": r.plugin_name,
                "total_bytes": r.total_bytes,
                "file_count": len(r.entries),
                "summary": r.summary,
                "error": r.error,
                "entries": [
                    {"path": str(e.path), "size_bytes": e.size_bytes, "description": e.description} for e in r.entries
                ],
            }
            for r in results
        ]
        return json.dumps(data)

    @method()
    def Clean(self, plugin_id: "s", entry_paths: "as") -> "s":  # type: ignore[override]
        """Clean a specific plugin, optionally with specific entries."""
        plugin = self._registry.get(plugin_id)
        if plugin is None:
            return json.dumps({"error": f"Plugin '{plugin_id}' not found"})

        # Check privileges for root plugins
        if plugin.requires_root and not is_root():
            return json.dumps({"error": "Root privileges required", "needs_auth": True})

        entries = None
        if entry_paths:
            last_scan = self._engine.get_last_scan(plugin_id)
            if last_scan:
                path_set = set(entry_paths)
                entries = [e for e in last_scan.entries if str(e.path) in path_set]

        results = self._engine.clean(
            plugin_ids=[plugin_id],
            entries_by_plugin={plugin_id: entries} if entries else None,
        )
        if results:
            self._tracker.record(results)
            self._tracker.save_session()
            for r in results:
                self.CleanProgress(r.plugin_id, r.freed_bytes, r.files_removed)
            data = [
                {
                    "plugin_id": r.plugin_id,
                    "freed_bytes": r.freed_bytes,
                    "files_removed": r.files_removed,
                    "errors": r.errors,
                }
                for r in results
            ]
            return json.dumps(data)
        return json.dumps([])

    @method()
    def CleanAll(self, plugin_ids: "as") -> "s":  # type: ignore[override]
        """Clean all specified plugins."""
        ids = list(plugin_ids) if plugin_ids else None
        results = self._engine.clean(plugin_ids=ids)
        self._tracker.record(results)
        self._tracker.save_session()

        data = [
            {
                "plugin_id": r.plugin_id,
                "freed_bytes": r.freed_bytes,
                "files_removed": r.files_removed,
                "errors": r.errors,
            }
            for r in results
        ]
        return json.dumps(data)

    @method()
    def GetStats(self, period: "s") -> "s":  # type: ignore[override]
        """Get statistics for a time period."""
        return json.dumps(self._tracker.get_stats(period))

    @method()
    def GetHistory(self) -> "s":  # type: ignore[override]
        """Get full session history."""
        return json.dumps(load_history())

    @signal()
    def ScanProgress(self, plugin_id: str, status: str) -> "(ss)":  # type: ignore[override]
        return [plugin_id, status]

    @signal()
    def CleanProgress(self, plugin_id: str, bytes_freed: int, files_done: int) -> "(sti)":  # type: ignore[override]
        return [plugin_id, bytes_freed, files_done]

    @signal()
    def PluginError(self, plugin_id: str, message: str) -> "(ss)":  # type: ignore[override]
        return [plugin_id, message]


async def run_service() -> None:
    """Start the D-Bus service."""
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    service = SweepDBusService()
    bus.export(_OBJECT_PATH, service)
    await bus.request_name(_BUS_NAME)
    log.info("D-Bus service started on %s", _BUS_NAME)
    await bus.wait_for_disconnect()


def start_service() -> None:
    """Entry point to start the D-Bus service."""
    asyncio.run(run_service())
