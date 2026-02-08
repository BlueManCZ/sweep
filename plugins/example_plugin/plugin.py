"""Example external plugin for Sweep.

This demonstrates how to create a custom cleaning plugin.
Place plugin directories in ~/.local/share/sweep/plugins/ to be discovered.
"""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult


class ExamplePlugin(CleanPlugin):
    """Example plugin that demonstrates the plugin interface."""

    @property
    def id(self) -> str:
        return "example"

    @property
    def name(self) -> str:
        return "Example Plugin"

    @property
    def description(self) -> str:
        return "An example plugin showing how to extend Sweep with custom cleaners."

    @property
    def category(self) -> str:
        return "application"

    def is_available(self) -> bool:
        return False  # Disabled by default — this is just an example

    def scan(self) -> ScanResult:
        return ScanResult(
            plugin_id=self.id,
            plugin_name=self.name,
            entries=[],
            total_bytes=0,
            summary="Example plugin — nothing to scan",
        )

    def clean(self, entries: list[FileEntry] | None = None) -> CleanResult:
        return CleanResult(plugin_id=self.id)
