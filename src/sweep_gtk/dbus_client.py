"""D-Bus client for connecting to the Sweep backend service."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult

log = logging.getLogger(__name__)

_BUS_NAME = "io.github.BlueManCZ.sweep"
_OBJECT_PATH = "/io/github/BlueManCZ/sweep"
_INTERFACE = "io.github.BlueManCZ.sweep.Manager"


class SweepClient:
    """Synchronous D-Bus client wrapping the Sweep backend.

    Falls back to direct engine calls if the D-Bus service is not available,
    making development and testing easier.
    """

    def __init__(self) -> None:
        self._use_direct = True  # Always use direct calls for simplicity
        self._engine = None
        self._tracker = None
        self._init_direct()

    def _init_direct(self) -> None:
        """Initialize direct engine access (no D-Bus)."""
        from sweep.core.engine import SweepEngine
        from sweep.core.plugin_loader import load_plugins
        from sweep.core.registry import PluginRegistry
        from sweep.core.tracker import Tracker

        registry = PluginRegistry()
        load_plugins(registry)
        self._engine = SweepEngine(registry)
        self._tracker = Tracker()

    def list_plugins(self) -> list[dict[str, Any]]:
        """List all available plugins."""
        plugins = self._engine.registry.get_all()
        result = []
        for p in plugins:
            available = p.is_available()
            entry: dict[str, Any] = {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "sort_order": p.sort_order,
                "icon": p.icon,
                "requires_root": p.requires_root,
                "risk_level": p.risk_level,
                "item_noun": p.item_noun,
                "available": available,
                "unavailable_reason": p.unavailable_reason,
                "has_items": _safe_has_items(p) if available else False,
            }
            if p.group:
                entry["group"] = {"id": p.group.id, "name": p.group.name, "description": p.group.description}
            result.append(entry)
        return result

    def _transform_scan_result(self, r: ScanResult) -> dict[str, Any]:
        """Transform a ScanResult into a serializable dict for the UI."""
        plugin = self._engine.registry.get(r.plugin_id)
        entry: dict[str, Any] = {
            "plugin_id": r.plugin_id,
            "plugin_name": r.plugin_name,
            "icon": plugin.icon if plugin else "application-x-executable-symbolic",
            "sort_order": plugin.sort_order if plugin else 50,
            "total_bytes": r.total_bytes,
            "file_count": len(r.entries),
            "summary": r.summary,
            "category": plugin.category if plugin else "user",
            "requires_root": plugin.requires_root if plugin else False,
            "item_noun": plugin.item_noun if plugin else "file",
            "entries": [
                {
                    "path": str(e.path),
                    "size_bytes": e.size_bytes,
                    "description": e.description,
                    "is_dir": e.path.is_dir(),
                    "is_leaf": e.is_leaf,
                    "child_count": e.file_count or 1,
                }
                for e in r.entries
            ],
        }
        if plugin and plugin.group:
            entry["group"] = {"id": plugin.group.id, "name": plugin.group.name}
        return entry

    @staticmethod
    def _transform_clean_result(r: CleanResult) -> dict[str, Any]:
        """Transform a CleanResult into a serializable dict for the UI."""
        return {
            "plugin_id": r.plugin_id,
            "freed_bytes": r.freed_bytes,
            "files_removed": r.files_removed,
            "errors": r.errors,
        }

    def scan(
        self,
        plugin_ids: list[str] | None = None,
        callback=None,
    ) -> list[dict[str, Any]]:
        """Scan for cleanable files."""
        results = self._engine.scan(
            plugin_ids=plugin_ids,
            on_progress=callback,
        )
        return [self._transform_scan_result(r) for r in results]

    def scan_streaming(
        self,
        plugin_ids: list[str],
        on_result: Callable[[dict[str, Any]], None] | None = None,
        on_progress: Callable[[str, str], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Scan with per-plugin streaming callbacks.

        Args:
            plugin_ids: Plugin IDs to scan.
            on_result: Called with each transformed result dict as it completes.
            on_progress: Optional progress callback (plugin_id, status).

        Returns:
            Full list of transformed result dicts.
        """
        transformed: list[dict[str, Any]] = []

        def _on_engine_result(scan_result: ScanResult) -> None:
            result_dict = self._transform_scan_result(scan_result)
            transformed.append(result_dict)
            if on_result:
                on_result(result_dict)

        self._engine.scan(
            plugin_ids=plugin_ids,
            on_progress=on_progress,
            on_result=_on_engine_result,
        )
        return transformed

    def _build_engine_entries(
        self,
        entries_by_plugin: dict[str, list[dict]],
    ) -> dict[str, list[FileEntry]]:
        """Convert UI entry dicts to engine FileEntry objects."""
        return {
            pid: [
                FileEntry(
                    path=Path(e["path"]),
                    size_bytes=e["size_bytes"],
                    description="",
                )
                for e in entries
            ]
            for pid, entries in entries_by_plugin.items()
        }

    def clean(
        self,
        plugin_ids: list[str] | None = None,
        entries_by_plugin: dict[str, list[dict]] | None = None,
    ) -> list[dict[str, Any]]:
        """Clean files for the specified plugins.

        Args:
            plugin_ids: Plugin IDs to clean. Ignored when entries_by_plugin is provided.
            entries_by_plugin: Per-plugin entry dicts with 'path' and 'size_bytes' keys.
                When provided, only the specified entries are cleaned.
        """
        engine_entries = None
        if entries_by_plugin is not None:
            plugin_ids = list(entries_by_plugin)
            engine_entries = self._build_engine_entries(entries_by_plugin)

        results = self._engine.clean(plugin_ids=plugin_ids, entries_by_plugin=engine_entries)
        self._tracker.record(results)
        self._tracker.save_session()
        return [self._transform_clean_result(r) for r in results]

    def clean_streaming(
        self,
        entries_by_plugin: dict[str, list[dict]],
        on_result: Callable[[dict[str, Any]], None] | None = None,
        on_progress: Callable[[str, str], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Clean with per-plugin streaming callbacks.

        Args:
            entries_by_plugin: Per-plugin entry dicts to clean.
            on_result: Called with each transformed result dict as it completes.
            on_progress: Optional progress callback (plugin_id, status).

        Returns:
            Full list of transformed result dicts.
        """
        plugin_ids = list(entries_by_plugin)
        engine_entries = self._build_engine_entries(entries_by_plugin)

        def _on_engine_result(clean_result: CleanResult) -> None:
            if on_result:
                on_result(self._transform_clean_result(clean_result))

        results = self._engine.clean(
            plugin_ids=plugin_ids,
            entries_by_plugin=engine_entries,
            on_progress=on_progress,
            on_result=_on_engine_result,
        )
        self._tracker.record(results)
        self._tracker.save_session()
        return [self._transform_clean_result(r) for r in results]

    def get_stats(self, period: str = "all") -> dict[str, Any]:
        """Get statistics for a time period."""
        return self._tracker.get_stats(period)

    def get_last_clean_time(self) -> str | None:
        """Return ISO timestamp of the most recent cleaning session, or None."""
        return self._tracker.get_last_clean_time()

    def get_history(self) -> dict[str, Any]:
        """Get full session history."""
        from sweep.storage import load_history

        return load_history()


def _safe_has_items(plugin: Any) -> bool:
    """Call has_items() with a fallback to True on error."""
    try:
        return plugin.has_items()
    except Exception:
        return True
