"""Scanning and cleaning orchestration engine."""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import ScanResult, FileEntry
from sweep.models.clean_result import CleanResult
from sweep.core.privileges import (
    is_root,
    pkexec_available,
    run_privileged_clean,
    PrivilegeError,
)
from sweep.core.registry import PluginRegistry

log = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str], None]  # (plugin_id, status_message)
ResultCallback = Callable[[ScanResult], None]
CleanResultCallback = Callable[[CleanResult], None]


class SweepEngine:
    """Orchestrates scanning and cleaning across plugins."""

    def __init__(self, registry: PluginRegistry) -> None:
        self.registry = registry
        self._last_scan: dict[str, ScanResult] = {}

    def scan(
        self,
        plugin_ids: list[str] | None = None,
        category: str | None = None,
        on_progress: ProgressCallback | None = None,
        on_result: ResultCallback | None = None,
    ) -> list[ScanResult]:
        """Scan for cleanable files using the specified plugins.

        Uses a small thread pool (4 workers) so multiple ``find``
        subprocesses can overlap.  Falls back to sequential scanning
        on single-core machines where threading adds overhead.

        Args:
            plugin_ids: Specific plugin IDs to scan. If None, scan all available.
            category: Filter plugins by category.
            on_progress: Optional callback for progress updates.
            on_result: Optional callback fired after each successful plugin scan.

        Returns:
            List of scan results from each plugin.
        """
        plugins = self._resolve_plugins(plugin_ids, category)
        if not plugins:
            return []

        results: list[ScanResult] = []

        if (os.cpu_count() or 1) > 1 and len(plugins) > 1:
            self._scan_parallel(plugins, results, on_progress, on_result)
        else:
            self._scan_sequential(plugins, results, on_progress, on_result)

        return results

    def _scan_sequential(
        self,
        plugins: list[CleanPlugin],
        results: list[ScanResult],
        on_progress: ProgressCallback | None,
        on_result: ResultCallback | None,
    ) -> None:
        """Scan plugins one at a time."""
        for plugin in plugins:
            if on_progress:
                on_progress(plugin.id, "scanning")
            try:
                result = plugin.scan()
                self._last_scan[plugin.id] = result
                results.append(result)
                if on_result:
                    on_result(result)
                if on_progress:
                    on_progress(plugin.id, "done")
            except Exception:
                log.exception("Plugin '%s' failed during scan", plugin.id)
                if on_progress:
                    on_progress(plugin.id, "error")

    def _scan_parallel(
        self,
        plugins: list[CleanPlugin],
        results: list[ScanResult],
        on_progress: ProgressCallback | None,
        on_result: ResultCallback | None,
    ) -> None:
        """Scan plugins concurrently via a small thread pool.

        Four workers let multiple ``find`` subprocesses overlap without
        saturating I/O on a single disk.
        """
        lock = threading.Lock()

        def _scan_plugin(plugin: CleanPlugin) -> None:
            if on_progress:
                on_progress(plugin.id, "scanning")
            try:
                result = plugin.scan()
                with lock:
                    self._last_scan[plugin.id] = result
                    results.append(result)
                if on_result:
                    on_result(result)
                if on_progress:
                    on_progress(plugin.id, "done")
            except Exception:
                log.exception("Plugin '%s' failed during scan", plugin.id)
                if on_progress:
                    on_progress(plugin.id, "error")

        max_workers = min(4, len(plugins))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_scan_plugin, plugin) for plugin in plugins]
            for future in futures:
                future.result()

    def clean(
        self,
        plugin_ids: list[str] | None = None,
        entries_by_plugin: dict[str, list[FileEntry]] | None = None,
        on_progress: ProgressCallback | None = None,
        on_result: CleanResultCallback | None = None,
    ) -> list[CleanResult]:
        """Clean files using the specified plugins.

        Root-requiring plugins are batched and escalated via pkexec
        (single password prompt). Non-root plugins are cleaned directly.

        Args:
            plugin_ids: Specific plugin IDs to clean. If None, clean all from last scan.
            entries_by_plugin: Optional per-plugin file entries to clean selectively.
            on_progress: Optional callback for progress updates.
            on_result: Optional callback fired after each plugin finishes cleaning.

        Returns:
            List of clean results from each plugin.
        """
        if plugin_ids is None:
            plugin_ids = list(self._last_scan.keys())

        results: list[CleanResult] = []
        root_entries: dict[str, list[FileEntry]] = {}

        for plugin_id in plugin_ids:
            plugin = self.registry.get(plugin_id)
            if plugin is None:
                log.warning("Plugin '%s' not found, skipping", plugin_id)
                continue

            # Collect root-requiring plugins for batch escalation
            if plugin.requires_root and not is_root():
                entries = entries_by_plugin.get(plugin_id) if entries_by_plugin else None
                if entries is None:
                    scan = self._last_scan.get(plugin_id)
                    entries = scan.entries if scan else []
                root_entries[plugin_id] = entries
                continue

            if on_progress:
                on_progress(plugin_id, "cleaning")

            entries = entries_by_plugin.get(plugin_id) if entries_by_plugin else None

            try:
                result = plugin.clean(entries=entries)
                results.append(result)
                if on_result:
                    on_result(result)
                if on_progress:
                    on_progress(plugin_id, "done")
            except Exception:
                log.exception("Plugin '%s' failed during clean", plugin_id)
                result = CleanResult(plugin_id=plugin_id, errors=["Plugin crashed during cleaning"])
                results.append(result)
                if on_result:
                    on_result(result)
                if on_progress:
                    on_progress(plugin_id, "error")

        # Escalate root plugins via pkexec in a single batch
        if root_entries:
            results.extend(self._clean_privileged(root_entries, on_progress, on_result))

        # Clear scan cache for cleaned plugins (keyed by parent plugin ID)
        for pid in plugin_ids:
            self._last_scan.pop(pid, None)

        return results

    def _clean_privileged(
        self,
        root_entries: dict[str, list[FileEntry]],
        on_progress: ProgressCallback | None = None,
        on_result: CleanResultCallback | None = None,
    ) -> list[CleanResult]:
        """Escalate cleaning of root-requiring plugins via pkexec."""
        if not pkexec_available():
            log.warning("pkexec not available, cannot escalate privileges")
            results = []
            for plugin_id in root_entries:
                plugin = self.registry.get(plugin_id)
                name = plugin.name if plugin else plugin_id
                result = CleanResult(
                    plugin_id=plugin_id,
                    errors=[f"Plugin '{name}' requires root privileges to clean " "(pkexec not available)"],
                )
                results.append(result)
                if on_result:
                    on_result(result)
                if on_progress:
                    on_progress(plugin_id, "error")
            return results

        # Serialize entries for the subprocess
        serialized: dict[str, list[dict]] = {}
        for plugin_id, entries in root_entries.items():
            serialized[plugin_id] = [
                {
                    "path": str(e.path),
                    "size_bytes": e.size_bytes,
                }
                for e in entries
            ]

        for plugin_id in root_entries:
            if on_progress:
                on_progress(plugin_id, "authenticating")

        try:
            raw_results = run_privileged_clean(serialized)
        except PrivilegeError as exc:
            log.warning("Privilege escalation failed: %s", exc)
            results = []
            for plugin_id in root_entries:
                result = CleanResult(
                    plugin_id=plugin_id,
                    errors=[str(exc)],
                )
                results.append(result)
                if on_result:
                    on_result(result)
                if on_progress:
                    on_progress(plugin_id, "error")
            return results

        # Convert raw dicts back to CleanResult objects
        results = []
        for raw in raw_results:
            result = CleanResult(
                plugin_id=raw["plugin_id"],
                freed_bytes=raw.get("freed_bytes", 0),
                files_removed=raw.get("files_removed", 0),
                errors=raw.get("errors", []),
            )
            results.append(result)
            if on_result:
                on_result(result)
            if on_progress:
                status = "done" if not raw.get("errors") else "error"
                on_progress(raw["plugin_id"], status)

        return results

    def get_last_scan(self, plugin_id: str) -> ScanResult | None:
        """Get the cached scan result for a plugin."""
        return self._last_scan.get(plugin_id)

    def _resolve_plugins(
        self,
        plugin_ids: list[str] | None,
        category: str | None,
    ) -> list[CleanPlugin]:
        """Resolve which plugins to operate on."""
        if plugin_ids:
            result: list[CleanPlugin] = []
            for pid in plugin_ids:
                plugin = self.registry.get(pid)
                if plugin is None:
                    log.warning("Plugin '%s' not found, skipping", pid)
                elif not plugin.is_available():
                    log.info("Plugin '%s' not available on this system, skipping", pid)
                else:
                    result.append(plugin)
            return result

        available = self.registry.get_available()
        if category:
            available = [p for p in available if p.category == category]
        return available
