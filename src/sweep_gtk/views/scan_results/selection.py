"""Tracks checkbox state for scan result selection."""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk


class _SelectionState:
    """Tracks checkbox state for scan result selection.

    Owns the three check-tracking lists and all toggle/query logic.
    Calls *on_changed* whenever the selection changes so the parent
    view can refresh its summary label and clean button.
    """

    def __init__(self, on_changed: Callable[[], None]) -> None:
        self._on_changed = on_changed
        self._module_checks: list[tuple[Gtk.CheckButton, str, list[Gtk.CheckButton]]] = []
        self._entry_checks: list[tuple[Gtk.CheckButton, dict]] = []
        self._group_checks: list[tuple[Gtk.CheckButton, list[Gtk.CheckButton]]] = []

    # -- Mutators --

    def clear(self) -> None:
        self._module_checks.clear()
        self._entry_checks.clear()
        self._group_checks.clear()

    def add_module(self, check: Gtk.CheckButton, plugin_id: str, child_checks: list[Gtk.CheckButton]) -> None:
        self._module_checks.append((check, plugin_id, child_checks))

    def add_entry(self, check: Gtk.CheckButton, info: dict) -> None:
        self._entry_checks.append((check, info))

    def add_group(self, check: Gtk.CheckButton, module_checks: list[Gtk.CheckButton]) -> None:
        self._group_checks.append((check, module_checks))

    @property
    def has_modules(self) -> bool:
        return bool(self._module_checks)

    def remove_plugin_ids(self, plugin_ids: set[str]) -> None:
        """Remove all tracking entries for the given plugin IDs (streaming rebuild)."""
        rendered_check_ids = {id(c) for c, pid, _ in self._module_checks if pid in plugin_ids}
        self._group_checks = [
            (gc, mc) for gc, mc in self._group_checks if not any(id(c) in rendered_check_ids for c in mc)
        ]
        self._module_checks = [(c, pid, cc) for c, pid, cc in self._module_checks if pid not in plugin_ids]
        self._entry_checks = [(c, info) for c, info in self._entry_checks if info["plugin_id"] not in plugin_ids]

    # -- Checkbox handlers --

    def set_all(self, active: bool) -> None:
        """Select or deselect all entry checkboxes."""
        for check, _ in self._entry_checks:
            check.set_active(active)
        for module_check, _, _ in self._module_checks:
            module_check.handler_block_by_func(self.on_module_toggled)
            module_check.set_active(active)
            module_check.set_inconsistent(False)
            module_check.handler_unblock_by_func(self.on_module_toggled)
        for group_check, _ in self._group_checks:
            group_check.handler_block_by_func(self.on_group_toggled)
            group_check.set_active(active)
            group_check.set_inconsistent(False)
            group_check.handler_unblock_by_func(self.on_group_toggled)
        self._on_changed()

    def on_group_toggled(self, group_check: Gtk.CheckButton, module_checks: list[Gtk.CheckButton]) -> None:
        """Toggle all module checkboxes when the group checkbox changes."""
        active = group_check.get_active()
        for module_check in module_checks:
            module_check.set_active(active)

    def on_module_toggled(self, module_check: Gtk.CheckButton, child_checks: list[Gtk.CheckButton]) -> None:
        """Toggle all child checkboxes when the module checkbox changes."""
        active = module_check.get_active()
        for check in child_checks:
            check.set_active(active)
        self._update_group_checks()
        self._on_changed()

    def on_entry_toggled(self, check: Gtk.CheckButton) -> None:
        """Update module and group checkboxes and summary when an entry is toggled."""
        for module_check, _, child_checks in self._module_checks:
            all_active = all(c.get_active() for c in child_checks)
            any_active = any(c.get_active() for c in child_checks)
            module_check.handler_block_by_func(self.on_module_toggled)
            module_check.set_active(all_active)
            module_check.set_inconsistent(any_active and not all_active)
            module_check.handler_unblock_by_func(self.on_module_toggled)
        self._update_group_checks()
        self._on_changed()

    def _update_group_checks(self) -> None:
        """Recompute group checkbox states from their module checks."""
        for group_check, module_checks in self._group_checks:
            all_on = all(c.get_active() and not c.get_inconsistent() for c in module_checks)
            any_on = any(c.get_active() or c.get_inconsistent() for c in module_checks)
            group_check.handler_block_by_func(self.on_group_toggled)
            group_check.set_active(all_on)
            group_check.set_inconsistent(any_on and not all_on)
            group_check.handler_unblock_by_func(self.on_group_toggled)

    # -- Queries --

    def get_selection_info(self) -> dict:
        """Compute selection details from active checkboxes.

        Returns dict with total_size, total_items, and per-module breakdown.
        """
        modules: dict[str, dict] = {}

        for check, info in self._entry_checks:
            if not check.get_active():
                continue
            name = info["plugin_name"]
            if name not in modules:
                modules[name] = {
                    "size": 0,
                    "check_ids": set(),
                    "requires_root": info.get("requires_root", False),
                }
            modules[name]["size"] += info["size_bytes"]
            modules[name]["check_ids"].add(id(check))

        return {
            "total_size": sum(m["size"] for m in modules.values()),
            "total_items": sum(len(m["check_ids"]) for m in modules.values()),
            "modules": [
                {
                    "name": name,
                    "size": m["size"],
                    "item_count": len(m["check_ids"]),
                    "requires_root": m["requires_root"],
                }
                for name, m in modules.items()
            ],
        }

    def get_entries_by_plugin(self) -> dict[str, list[dict]]:
        """Build per-plugin entry lists from active checkboxes for the clean operation."""
        entries_by_plugin: dict[str, list[dict]] = {}
        for check, info in self._entry_checks:
            if not check.get_active():
                continue
            entries_by_plugin.setdefault(info["plugin_id"], []).append(
                {"path": info["path"], "size_bytes": info["size_bytes"]}
            )
        return entries_by_plugin

    def disable_all(self) -> None:
        """Disable all checkboxes (post-clean)."""
        for check, _ in self._entry_checks:
            check.set_sensitive(False)
        for check, _, _ in self._module_checks:
            check.set_sensitive(False)
        for check, _ in self._group_checks:
            check.set_sensitive(False)
