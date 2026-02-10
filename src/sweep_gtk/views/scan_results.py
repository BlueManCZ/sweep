"""Scan results view — preview with selective cleaning."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, GLib, Pango

from sweep.settings import Settings
from sweep.utils import bytes_to_human, format_elapsed as _format_elapsed
from sweep_gtk.constants import CATEGORY_LABELS
from sweep_gtk.widgets import icon_label as _icon_label
from sweep_gtk.dialogs import show_confirm_dialog
from sweep_gtk.views.settings import SettingsView

_SORT_KEY = "results.sort_by_size"

if TYPE_CHECKING:
    from sweep_gtk.window import SweepWindow


class ScanResultsView(Gtk.Box):
    """View showing scan results with per-item selection."""

    def __init__(self, window: SweepWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self._scan_results: list[dict] = []
        self._module_checks: list[tuple[Gtk.CheckButton, str, list[Gtk.CheckButton]]] = []
        self._entry_checks: list[tuple[Gtk.CheckButton, dict]] = []
        self._group_checks: list[tuple[Gtk.CheckButton, list[Gtk.CheckButton]]] = []
        self._groups: list[Adw.PreferencesGroup] = []
        self._sort_by_size: bool = Settings.instance().get(_SORT_KEY, False)

        # Streaming scan state
        self._show_empty_results: bool = True
        self._scan_start_time: float = 0.0
        self._scanning: bool = False
        self._scan_total: int = 0
        self._scan_completed: int = 0
        self._scan_generation: int = 0
        self._group_pending: dict[str, list[dict]] = {}
        self._group_expected: dict[str, int] = {}
        self._group_widgets: dict[str, Adw.PreferencesGroup] = {}
        self._empty_results: list[dict] = []

        # Per-plugin clean status widgets: plugin_id -> (spinner, checkmark, label)
        self._clean_status: dict[str, tuple[Gtk.Spinner, Gtk.Image, Gtk.Label]] = {}

        # Track expander rows for expanded-state preservation across re-sorts
        # Keys are plugin_id (standalone modules) or group_id (group expanders)
        self._expander_rows: dict[str, Adw.ExpanderRow] = {}
        self._saved_expanded: dict[str, bool] = {}

        # Category-based PreferencesGroups (mirrors Modules view layout)
        self._category_groups: dict[str, Adw.PreferencesGroup] = {}

        # Per-category sorted children for streaming insertion order
        # Maps cat_id -> list of (sort_key, widget) pairs
        self._category_children: dict[str, list[tuple[tuple, Gtk.Widget]]] = {}

        # Clean progress tracking
        self._clean_total: int = 0
        self._clean_completed: int = 0
        self._clean_done: bool = False

        # Progress indicator (shared by scan & clean)
        # Adw.Banner provides the styled background; spinner + progress bar sit below it.
        # Everything is wrapped in one Revealer so it animates as a single unit.
        self._progress_revealer = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
            reveal_child=False,
        )
        progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._progress_banner = Adw.Banner(revealed=True)
        progress_box.append(self._progress_banner)

        self._progress_bar_row = Gtk.Box(
            spacing=8,
            margin_start=12,
            margin_end=12,
            margin_top=6,
            margin_bottom=6,
        )
        self._progress_spinner = Gtk.Spinner()
        self._progress_bar_row.append(self._progress_spinner)
        self._progress_bar = Gtk.ProgressBar(hexpand=True, valign=Gtk.Align.CENTER)
        self._progress_bar_row.append(self._progress_bar)
        progress_box.append(self._progress_bar_row)

        self._progress_revealer.set_child(progress_box)
        self.append(self._progress_revealer)

        # Floating toolbar with selection and sort controls (appended after scrolled)
        self._toolbar_revealer = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.SLIDE_UP,
            reveal_child=False,
        )
        toolbar = Gtk.Box(spacing=6, margin_start=12, margin_end=12)

        select_all_btn = Gtk.Button(child=_icon_label("edit-select-all-symbolic", "Select All"))
        select_all_btn.connect("clicked", lambda _: self._set_all_entries(True))
        toolbar.append(select_all_btn)

        select_none_btn = Gtk.Button(child=_icon_label("edit-clear-symbolic", "Select None"))
        select_none_btn.connect("clicked", lambda _: self._set_all_entries(False))
        toolbar.append(select_none_btn)

        spacer = Gtk.Box(hexpand=True)
        toolbar.append(spacer)

        self.sort_btn = Gtk.ToggleButton(
            child=_icon_label("view-sort-descending-symbolic", "Sort by Size"),
            active=self._sort_by_size,
        )
        self.sort_btn.set_tooltip_text("Sort entries by size (largest first)")
        self.sort_btn.connect("toggled", self._on_sort_toggled)
        toolbar.append(self.sort_btn)

        toolbar_clamp = Adw.Clamp(maximum_size=600, child=toolbar, margin_top=6, margin_bottom=6)
        self._toolbar_revealer.set_child(toolbar_clamp)

        # Scrolled content
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        self.append(scrolled)

        self.prefs_page = Adw.PreferencesPage()
        scrolled.set_child(self.prefs_page)

        # Empty state
        self.empty_status = Adw.StatusPage()
        self.empty_status.set_icon_name("edit-find-symbolic")
        self.empty_status.set_title("No Scan Results")
        self.empty_status.set_description("Run a scan to find reclaimable space.")

        empty_buttons = Gtk.Box(
            spacing=12,
            halign=Gtk.Align.CENTER,
            margin_top=12,
        )
        safe_scan_btn = Gtk.Button(
            child=_icon_label("security-high-symbolic", "Safe Scan"),
        )
        safe_scan_btn.add_css_class("pill")
        safe_scan_btn.connect("clicked", self._on_safe_scan)
        empty_buttons.append(safe_scan_btn)

        full_scan_btn = Gtk.Button(
            child=_icon_label("edit-select-all-symbolic", "Full Scan"),
        )
        full_scan_btn.add_css_class("pill")
        full_scan_btn.connect("clicked", self._on_full_scan)
        empty_buttons.append(full_scan_btn)

        self.empty_status.set_child(empty_buttons)
        self._empty_group = self._wrap_in_group(self.empty_status)
        self.prefs_page.add(self._empty_group)
        self._groups.append(self._empty_group)

        # Bottom toolbar (selection and sort controls)
        self.append(self._toolbar_revealer)

        # Bottom bar with summary and clean button
        self.action_bar = Gtk.ActionBar()
        self.action_bar.set_visible(False)
        self.append(self.action_bar)

        self.summary_label = Gtk.Label(label="")
        self.summary_label.add_css_class("heading")
        self.action_bar.pack_start(self.summary_label)

        self.clean_btn = Gtk.Button(label="Clean Selected")
        self.clean_btn.add_css_class("destructive-action")
        self.clean_btn.connect("clicked", self._on_clean_clicked)
        self.action_bar.pack_end(self.clean_btn)

    def _on_safe_scan(self, button: Gtk.Button) -> None:
        """Launch a scan with only safe-risk plugins."""
        plugins = self.window.client.list_plugins()
        safe_ids = [p["id"] for p in plugins if p["available"] and p["risk_level"] == "safe"]
        self.window.launch_scan(safe_ids)

    def _on_full_scan(self, button: Gtk.Button) -> None:
        """Launch a scan with all available plugins."""
        plugins = self.window.client.list_plugins()
        all_ids = [p["id"] for p in plugins if p["available"]]
        self.window.launch_scan(all_ids)

    def _get_or_create_category_group(self, cat_id: str) -> Adw.PreferencesGroup:
        """Get an existing category group or create a new one."""
        if cat_id in self._category_groups:
            return self._category_groups[cat_id]

        cat_group = Adw.PreferencesGroup(
            title=CATEGORY_LABELS.get(cat_id, cat_id.replace("_", " ").title()),
        )
        self.prefs_page.add(cat_group)
        self._groups.append(cat_group)
        self._category_groups[cat_id] = cat_group
        return cat_group

    def _wrap_in_group(self, widget: Gtk.Widget) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup()
        group.add(widget)
        return group

    def _on_sort_toggled(self, button: Gtk.ToggleButton) -> None:
        """Re-populate the view when sort toggle changes."""
        self._sort_by_size = button.get_active()
        Settings.instance().set(_SORT_KEY, self._sort_by_size)

        # Save expanded state so rows are created already expanded/collapsed
        self._saved_expanded = {key: row.get_expanded() for key, row in self._expander_rows.items()}
        self.populate(self._scan_results)
        self._saved_expanded = {}

    def populate(self, results: list[dict]) -> None:
        """Populate the view with scan results."""
        self._scan_results = results
        self._module_checks.clear()
        self._entry_checks.clear()
        self._group_checks.clear()
        self._expander_rows.clear()
        self._clean_status.clear()
        self._category_groups.clear()

        # Clear existing groups
        for group in self._groups:
            self.prefs_page.remove(group)
        self._groups.clear()

        actionable = [r for r in results if r["total_bytes"] > 0]
        empty = [r for r in results if r["total_bytes"] == 0]

        if not actionable and not empty:
            self._empty_group = self._wrap_in_group(self.empty_status)
            self.prefs_page.add(self._empty_group)
            self._groups.append(self._empty_group)
            self.action_bar.set_visible(False)
            self._toolbar_revealer.set_reveal_child(False)
            return

        # Group actionable results by category, then by plugin group vs standalone
        by_category: dict[str, list[dict]] = {}
        for result in actionable:
            cat = result.get("category", "user")
            by_category.setdefault(cat, []).append(result)

        # Build category groups in CATEGORY_LABELS order (matching Modules view)
        for cat_id in CATEGORY_LABELS:
            cat_results = by_category.get(cat_id)
            if not cat_results:
                continue
            self._populate_category(cat_id, cat_results)

        # Handle any categories not in CATEGORY_LABELS
        for cat_id, cat_results in by_category.items():
            if cat_id not in CATEGORY_LABELS:
                self._populate_category(cat_id, cat_results)

        if empty and self._show_empty_results:
            self._populate_empty_plugins(empty)

        has_actionable = bool(actionable)
        self.action_bar.set_visible(has_actionable)
        self._toolbar_revealer.set_reveal_child(has_actionable)
        self._update_summary()

    def _populate_category(self, cat_id: str, results: list[dict]) -> None:
        """Populate a single category group with its results."""
        cat_group = Adw.PreferencesGroup(
            title=CATEGORY_LABELS.get(cat_id, cat_id.replace("_", " ").title()),
        )
        self.prefs_page.add(cat_group)
        self._groups.append(cat_group)
        self._category_groups[cat_id] = cat_group

        # Partition into plugin groups and standalone
        grouped: dict[str, list[dict]] = {}
        standalone: list[dict] = []
        for result in results:
            g = result.get("group")
            if g:
                grouped.setdefault(g["id"], []).append(result)
            else:
                standalone.append(result)

        # Build top-level items with sort keys for ordering within category
        top_items: list[tuple[tuple, str, object]] = []
        for group_id, member_results in grouped.items():
            if self._sort_by_size:
                member_results.sort(key=lambda r: r["total_bytes"], reverse=True)
            else:
                member_results.sort(key=lambda r: (r.get("sort_order", 50), r["plugin_name"].lower()))
            group_total = sum(r["total_bytes"] for r in member_results)
            best = member_results[0]
            if self._sort_by_size:
                sort_key = (-group_total, best["plugin_name"].lower())
            else:
                sort_key = (best.get("sort_order", 50), best["plugin_name"].lower())
            top_items.append((sort_key, "group", member_results))

        for result in standalone:
            if self._sort_by_size:
                sort_key = (-result["total_bytes"], result["plugin_name"].lower())
            else:
                sort_key = (result.get("sort_order", 50), result["plugin_name"].lower())
            top_items.append((sort_key, "standalone", result))

        top_items.sort(key=lambda x: x[0])

        for _, kind, data in top_items:
            if kind == "group":
                self._populate_group_result(data, cat_group)
            else:
                self._populate_simple_plugin(data, cat_group)

    def _create_module_row(self, result: dict) -> tuple[Adw.ExpanderRow, Gtk.CheckButton, list[Gtk.CheckButton]]:
        """Create a module-level expander row with entry rows inside.

        Returns (module_row, module_check, child_checks).
        """
        total_files = sum(e.get("child_count", 1) for e in result["entries"])
        noun = result.get("item_noun", "file")

        module_row = Adw.ExpanderRow()
        module_row.set_title(result["plugin_name"])
        module_row.set_subtitle(
            f"{bytes_to_human(result['total_bytes'])}  \u00b7  "
            f"{total_files:,} {noun}{'s' if total_files != 1 else ''}  \u00b7  "
            f"{result['file_count']} entr{'ies' if result['file_count'] != 1 else 'y'}"
        )
        plugin_id = result["plugin_id"]
        if plugin_id in self._saved_expanded:
            module_row.set_expanded(self._saved_expanded[plugin_id])
        self._expander_rows[plugin_id] = module_row

        module_check = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
        module_row.add_prefix(module_check)

        module_icon = Gtk.Image.new_from_icon_name(result.get("icon", "application-x-executable-symbolic"))
        module_row.add_prefix(module_icon)

        # Info icon with filesystem path tooltip
        entry_paths = [Path(e["path"]) for e in result["entries"]]
        if entry_paths:
            info_icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
            info_icon.set_tooltip_text(str(_common_parent(entry_paths)))
            info_icon.add_css_class("dim-label")
            info_icon.set_valign(Gtk.Align.CENTER)
            module_row.add_suffix(info_icon)

        # Clean status widgets (hidden until cleaning starts)
        clean_spinner = Gtk.Spinner(visible=False, valign=Gtk.Align.CENTER)
        clean_check = Gtk.Image(visible=False, valign=Gtk.Align.CENTER)
        clean_label = Gtk.Label(visible=False, valign=Gtk.Align.CENTER)
        clean_label.add_css_class("caption")
        clean_label.add_css_class("dim-label")
        module_row.add_suffix(clean_spinner)
        module_row.add_suffix(clean_check)
        module_row.add_suffix(clean_label)
        self._clean_status[result["plugin_id"]] = (clean_spinner, clean_check, clean_label)

        # Entry rows inside the expander
        entries = result["entries"]
        if self._sort_by_size:
            entries = sorted(entries, key=lambda e: e["size_bytes"], reverse=True)

        child_checks: list[Gtk.CheckButton] = []
        for entry in entries:
            entry_path = Path(entry["path"])
            is_dir = entry.get("is_dir", False)
            child_count = entry.get("child_count", 1)

            row = Adw.ActionRow()

            icon = "folder-symbolic" if is_dir else "text-x-generic-symbolic"
            row.set_title(entry_path.name)
            row.add_prefix(Gtk.Image.new_from_icon_name(icon))

            if is_dir and child_count > 0:
                row.set_subtitle(f"{child_count:,} file{'s' if child_count != 1 else ''}")

            # Size label
            if is_dir and entry["size_bytes"] == 0:
                size_text = "Empty folder"
            else:
                size_text = bytes_to_human(entry["size_bytes"])
            size_label = Gtk.Label(label=size_text)
            size_label.add_css_class("numeric")
            size_label.add_css_class("dim-label")
            row.add_suffix(size_label)

            # Browse files button for non-empty directories
            if is_dir and child_count > 0:
                view_btn = Gtk.Button.new_from_icon_name("view-list-symbolic")
                view_btn.add_css_class("flat")
                view_btn.set_valign(Gtk.Align.CENTER)
                view_btn.set_tooltip_text("Browse files")
                view_btn.connect("clicked", self._on_view_files, entry["path"])
                row.add_suffix(view_btn)

            # Per-entry checkbox
            check = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
            check.connect("toggled", self._on_entry_toggled)
            row.add_suffix(check)
            row.set_activatable_widget(check)

            child_checks.append(check)
            self._entry_checks.append(
                (
                    check,
                    {
                        "plugin_id": result["plugin_id"],
                        "plugin_name": result["plugin_name"],
                        "path": entry["path"],
                        "size_bytes": entry["size_bytes"],
                        "requires_root": result.get("requires_root", False),
                    },
                )
            )

            module_row.add_row(row)

        # Wire module checkbox to toggle all children
        module_check.connect("toggled", self._on_module_toggled, child_checks)
        self._module_checks.append((module_check, result["plugin_id"], child_checks))

        return module_row, module_check, child_checks

    def _populate_simple_plugin(
        self,
        result: dict,
        cat_group: Adw.PreferencesGroup | None = None,
    ) -> None:
        """Populate a standalone plugin row.

        Args:
            result: Scan result dict.
            cat_group: Category group to add the row to. If None, creates a new group.
        """
        if cat_group is None:
            cat_group = Adw.PreferencesGroup()
            self.prefs_page.add(cat_group)
            self._groups.append(cat_group)

        module_row, _, _ = self._create_module_row(result)
        cat_group.add(module_row)

    def _create_group_member_row(self, result: dict) -> tuple[Adw.ActionRow, Gtk.CheckButton]:
        """Create a flat member row for a grouped plugin.

        All entries are selected/deselected as a unit via one checkbox.
        Returns (member_row, member_check).
        """
        total_files = sum(e.get("child_count", 1) for e in result["entries"])
        noun = result.get("item_noun", "file")

        row = Adw.ActionRow()
        row.set_title(result["plugin_name"])
        row.set_subtitle(
            f"{bytes_to_human(result['total_bytes'])}  \u00b7  "
            f"{total_files:,} {noun}{'s' if total_files != 1 else ''}  \u00b7  "
            f"{result['file_count']} entr{'ies' if result['file_count'] != 1 else 'y'}"
        )
        row.add_prefix(Gtk.Image.new_from_icon_name(result.get("icon", "application-x-executable-symbolic")))

        # Info icon with filesystem path tooltip
        entry_paths = [Path(e["path"]) for e in result["entries"]]
        if entry_paths:
            info_icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
            info_icon.set_tooltip_text(str(_common_parent(entry_paths)))
            info_icon.add_css_class("dim-label")
            info_icon.set_valign(Gtk.Align.CENTER)
            row.add_suffix(info_icon)

        # Clean status widgets (hidden until cleaning starts)
        clean_spinner = Gtk.Spinner(visible=False, valign=Gtk.Align.CENTER)
        clean_check_img = Gtk.Image(visible=False, valign=Gtk.Align.CENTER)
        clean_label = Gtk.Label(visible=False, valign=Gtk.Align.CENTER)
        clean_label.add_css_class("caption")
        clean_label.add_css_class("dim-label")
        row.add_suffix(clean_spinner)
        row.add_suffix(clean_check_img)
        row.add_suffix(clean_label)
        self._clean_status[result["plugin_id"]] = (clean_spinner, clean_check_img, clean_label)

        # Size label
        size_label = Gtk.Label(label=bytes_to_human(result["total_bytes"]))
        size_label.add_css_class("numeric")
        size_label.add_css_class("dim-label")
        row.add_suffix(size_label)

        # Browse button — shows all entries for this plugin
        if entry_paths:
            view_btn = Gtk.Button.new_from_icon_name("view-list-symbolic")
            view_btn.add_css_class("flat")
            view_btn.set_valign(Gtk.Align.CENTER)
            view_btn.set_tooltip_text("Browse files")
            browse_path = _common_parent(entry_paths)

            if all(e.get("is_leaf", False) for e in result["entries"]):
                # Leaf entries (e.g. packages) — list them directly
                leaf_items = [
                    (str(p.relative_to(browse_path)), e["size_bytes"], e.get("description", ""))
                    for p, e in zip(entry_paths, result["entries"])
                ]
                view_btn.connect("clicked", self._on_view_leaf_entries, str(browse_path), leaf_items, noun)
            else:
                view_btn.connect("clicked", self._on_view_files, str(browse_path))
            row.add_suffix(view_btn)

        # Single checkbox for the whole plugin
        member_check = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
        row.add_suffix(member_check)
        row.set_activatable_widget(member_check)

        # Hidden entry checks — all controlled by member_check
        hidden_checks: list[Gtk.CheckButton] = []
        for entry in result["entries"]:
            check = Gtk.CheckButton(active=True)
            check.set_visible(False)
            hidden_checks.append(check)
            self._entry_checks.append(
                (
                    check,
                    {
                        "plugin_id": result["plugin_id"],
                        "plugin_name": result["plugin_name"],
                        "path": entry["path"],
                        "size_bytes": entry["size_bytes"],
                        "requires_root": result.get("requires_root", False),
                    },
                )
            )

        # Wire member checkbox to toggle all hidden entry checks
        member_check.connect("toggled", self._on_module_toggled, hidden_checks)
        self._module_checks.append((member_check, result["plugin_id"], hidden_checks))

        return row, member_check

    def _populate_group_result(
        self,
        member_results: list[dict],
        cat_group: Adw.PreferencesGroup | None = None,
    ) -> None:
        """Populate a group of related plugins under a group expander.

        Args:
            member_results: List of scan result dicts for group members.
            cat_group: Category group to add the row to. If None, creates a new group.
        """
        group_meta = member_results[0]["group"]
        group_icon = member_results[0].get("icon", "application-x-executable-symbolic")

        # Compute group totals
        group_total_bytes = sum(r["total_bytes"] for r in member_results)
        group_total_files = sum(sum(e.get("child_count", 1) for e in r["entries"]) for r in member_results)
        group_entry_count = sum(r["file_count"] for r in member_results)

        if cat_group is None:
            cat_group = Adw.PreferencesGroup()
            self.prefs_page.add(cat_group)
            self._groups.append(cat_group)

        # Group-level expander row
        group_id = group_meta["id"]
        group_row = Adw.ExpanderRow()
        group_row.set_title(group_meta["name"])
        group_row.set_subtitle(
            f"{bytes_to_human(group_total_bytes)}  \u00b7  "
            f"{group_total_files:,} file{'s' if group_total_files != 1 else ''}  \u00b7  "
            f"{group_entry_count} entr{'ies' if group_entry_count != 1 else 'y'}"
        )
        if group_id in self._saved_expanded:
            group_row.set_expanded(self._saved_expanded[group_id])
        self._expander_rows[group_id] = group_row

        group_check = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
        group_row.add_prefix(group_check)
        group_row.add_prefix(Gtk.Image.new_from_icon_name(group_icon))

        cat_group.add(group_row)

        # Create flat member rows inside the group expander
        member_module_checks: list[Gtk.CheckButton] = []
        for result in member_results:
            member_row, member_check = self._create_group_member_row(result)
            group_row.add_row(member_row)
            member_module_checks.append(member_check)

        # Wire group checkbox → all member module checks
        group_check.connect("toggled", self._on_group_toggled, member_module_checks)
        self._group_checks.append((group_check, member_module_checks))

    def _populate_empty_plugins(self, empty_results: list[dict]) -> None:
        """Show plugins that were scanned but found nothing."""
        group = Adw.PreferencesGroup(
            title="Nothing Found",
            description="These modules were scanned but had nothing to clean",
        )
        self.prefs_page.add(group)
        self._groups.append(group)

        for result in empty_results:
            row = Adw.ActionRow()
            row.set_title(result["plugin_name"])
            row.add_prefix(Gtk.Image.new_from_icon_name(result.get("icon", "application-x-executable-symbolic")))
            row.add_css_class("dim-label")

            badge = Gtk.Label(label="Empty")
            badge.add_css_class("dim-label")
            badge.add_css_class("caption")
            row.add_suffix(badge)

            group.add(row)

    # -- Streaming scan --

    def begin_streaming_scan(
        self,
        total_plugins: int,
        group_info: dict[str, int],
        *,
        show_empty: bool = True,
    ) -> None:
        """Prepare the view for incremental scan results.

        Args:
            total_plugins: Total number of plugins being scanned.
            group_info: Mapping of group_id to expected member count.
            show_empty: Whether to show modules that found nothing.
        """
        self._show_empty_results = show_empty
        self._scan_start_time = time.monotonic()
        # Clear all existing state
        self._scan_results.clear()
        self._module_checks.clear()
        self._entry_checks.clear()
        self._group_checks.clear()
        self._clean_status.clear()
        for group in self._groups:
            self.prefs_page.remove(group)
        self._groups.clear()

        self._group_pending.clear()
        self._group_expected = dict(group_info)
        self._group_widgets.clear()
        self._empty_results.clear()
        self._expander_rows.clear()
        self._category_groups.clear()
        self._category_children.clear()

        # Set streaming state
        self._scanning = True
        self._scan_total = total_plugins
        self._scan_completed = 0
        self._scan_generation += 1

        # Reset clean-done state and button styling
        self._clean_done = False
        self.clean_btn.set_label("Clean Selected")
        self.clean_btn.remove_css_class("suggested-action")
        self.clean_btn.add_css_class("destructive-action")

        # Show progress indicator, hide action bar and toolbar
        self._progress_banner.set_title(f"Scanning 0/{total_plugins} modules\u2026")
        self._progress_bar.set_fraction(0.0)
        self._progress_bar_row.set_visible(True)
        self._progress_spinner.set_spinning(True)
        self._progress_revealer.set_reveal_child(True)
        self.action_bar.set_visible(False)
        self._toolbar_revealer.set_reveal_child(False)
        self.sort_btn.set_sensitive(False)

    def add_streaming_result(self, result: dict, generation: int) -> None:
        """Add a single scan result during streaming. Called via GLib.idle_add.

        Args:
            result: Transformed scan result dict.
            generation: Scan generation to detect stale callbacks.
        """
        if generation != self._scan_generation:
            return

        self._scan_completed += 1
        self._scan_results.append(result)
        self._progress_banner.set_title(f"Scanning {self._scan_completed}/{self._scan_total} modules\u2026")
        if self._scan_total > 0:
            self._progress_bar.set_fraction(self._scan_completed / self._scan_total)

        group = result.get("group")
        is_empty = result["total_bytes"] == 0

        if is_empty:
            self._empty_results.append(result)

        cat_id = result.get("category", "user")

        if group:
            # Always track group membership (even empty results count toward
            # completion so partial groups don't get stuck with "Scanning N more…")
            self._add_streaming_group_result(result, group, cat_id)
        elif not is_empty:
            cat_group = self._get_or_create_category_group(cat_id)
            self._populate_simple_plugin(result, cat_group)
            # Track for sorted insertion within category
            sort_key = (result.get("sort_order", 50), result["plugin_name"].lower())
            self._category_children.setdefault(cat_id, []).append((sort_key, self._expander_rows[result["plugin_id"]]))
            self._sort_category_items(cat_id)
        else:
            return  # standalone empty result — nothing to render yet

        # Re-sort categories on the page
        self._resort_groups()

        # Show action bar and toolbar once we have actionable results
        if self._module_checks:
            self.action_bar.set_visible(True)
            self._toolbar_revealer.set_reveal_child(True)
            self._update_summary()

    def _add_streaming_group_result(
        self,
        result: dict,
        group: dict,
        cat_id: str,
    ) -> None:
        """Handle a streaming result that belongs to a plugin group."""
        group_id = group["id"]
        self._group_pending.setdefault(group_id, []).append(result)
        pending = self._group_pending[group_id]
        expected = self._group_expected.get(group_id, 1)

        # Only non-empty members produce UI rows
        actionable = [r for r in pending if r["total_bytes"] > 0]

        # Remove old group expander row if it exists (we'll rebuild)
        old_entry = self._group_widgets.pop(group_id, None)
        if old_entry:
            old_cat_group, old_expander = old_entry
            old_cat_group.remove(old_expander)
            # Remove from category children tracking
            if cat_id in self._category_children:
                self._category_children[cat_id] = [
                    (sk, w) for sk, w in self._category_children[cat_id] if w is not old_expander
                ]
            # Clean up checks for previously rendered (non-empty) members
            previously_rendered = {r["plugin_id"] for r in actionable}
            if result["total_bytes"] > 0:
                previously_rendered.discard(result["plugin_id"])
            # Identify stale group_checks via their module check refs
            rendered_check_ids = {id(c) for c, pid, _ in self._module_checks if pid in previously_rendered}
            self._group_checks = [
                (gc, mc) for gc, mc in self._group_checks if not any(id(c) in rendered_check_ids for c in mc)
            ]
            self._module_checks = [(c, pid, cc) for c, pid, cc in self._module_checks if pid not in previously_rendered]
            self._entry_checks = [
                (c, info) for c, info in self._entry_checks if info["plugin_id"] not in previously_rendered
            ]
            for pid in previously_rendered:
                self._clean_status.pop(pid, None)

        if not actionable:
            # All received members are empty — no group widget to display
            return

        cat_group = self._get_or_create_category_group(cat_id)
        remaining = expected - len(pending)

        # Sort actionable members for display order
        actionable.sort(key=lambda r: (r.get("sort_order", 50), r["plugin_name"].lower()))

        if remaining <= 0:
            # All members received — build final group with non-empty members
            self._populate_group_result(actionable, cat_group)
            # Track the expander row (last one added to _expander_rows for this group)
            self._group_widgets[group_id] = (cat_group, self._expander_rows[group["id"]])
        else:
            # Partial group — show non-empty members + loading indicator
            self._build_partial_group(actionable, group, remaining, cat_group)

        # Track for sorted insertion within category
        best = actionable[0]
        group_sort_key = (best.get("sort_order", 50), best["plugin_name"].lower())
        group_widget = self._group_widgets[group_id][1]
        self._category_children.setdefault(cat_id, []).append((group_sort_key, group_widget))
        self._sort_category_items(cat_id)

    def _build_partial_group(
        self,
        member_results: list[dict],
        group_meta: dict,
        remaining: int,
        cat_group: Adw.PreferencesGroup,
    ) -> None:
        """Build a temporary group widget with partial results and a loading row.

        Args:
            member_results: Non-empty member results to display.
            group_meta: Group metadata (id, name).
            remaining: Number of members still being scanned.
            cat_group: Category group to add the expander to.
        """
        group_id = group_meta["id"]
        group_icon = member_results[0].get("icon", "application-x-executable-symbolic")

        group_total_bytes = sum(r["total_bytes"] for r in member_results)
        group_total_files = sum(sum(e.get("child_count", 1) for e in r["entries"]) for r in member_results)
        group_entry_count = sum(r["file_count"] for r in member_results)

        group_row = Adw.ExpanderRow()
        group_row.set_title(group_meta["name"])
        group_row.set_subtitle(
            f"{bytes_to_human(group_total_bytes)}  \u00b7  "
            f"{group_total_files:,} file{'s' if group_total_files != 1 else ''}  \u00b7  "
            f"{group_entry_count} entr{'ies' if group_entry_count != 1 else 'y'}"
        )

        group_check = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
        group_row.add_prefix(group_check)
        group_row.add_prefix(Gtk.Image.new_from_icon_name(group_icon))

        cat_group.add(group_row)
        self._group_widgets[group_id] = (cat_group, group_row)

        member_module_checks: list[Gtk.CheckButton] = []
        for result in member_results:
            member_row, member_check = self._create_group_member_row(result)
            group_row.add_row(member_row)
            member_module_checks.append(member_check)

        # Loading indicator row
        loading_row = Adw.ActionRow()
        loading_box = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        spinner = Gtk.Spinner(spinning=True)
        loading_box.append(spinner)
        loading_box.append(
            Gtk.Label(
                label=f"Scanning {remaining} more\u2026",
                css_classes=["dim-label", "caption"],
            )
        )
        loading_row.add_prefix(loading_box)
        group_row.add_row(loading_row)

        group_check.connect("toggled", self._on_group_toggled, member_module_checks)
        self._group_checks.append((group_check, member_module_checks))

    def _resort_groups(self) -> None:
        """Re-sort category groups on the page to match CATEGORY_LABELS order."""
        if len(self._groups) <= 1:
            return

        # Build sort key: category order from CATEGORY_LABELS, unknown categories last
        cat_order = {cat_id: i for i, cat_id in enumerate(CATEGORY_LABELS)}

        def _sort_key(g: Adw.PreferencesGroup) -> int:
            for cat_id, cat_group in self._category_groups.items():
                if cat_group is g:
                    return cat_order.get(cat_id, len(cat_order))
            return len(cat_order) + 1  # unknown groups at end

        for g in self._groups:
            self.prefs_page.remove(g)
        self._groups.sort(key=_sort_key)
        for g in self._groups:
            self.prefs_page.add(g)

    def _sort_category_items(self, cat_id: str) -> None:
        """Re-sort items within a category group to maintain correct display order."""
        children = self._category_children.get(cat_id)
        if not children or len(children) <= 1:
            return
        cat_group = self._category_groups[cat_id]
        for _, widget in children:
            cat_group.remove(widget)
        children.sort(key=lambda x: x[0])
        for _, widget in children:
            cat_group.add(widget)

    def finish_streaming_scan(self) -> float:
        """Finalize the streaming scan — show summary banner, rebuild with correct ordering.

        Returns:
            Elapsed scan time in seconds.
        """
        elapsed = time.monotonic() - self._scan_start_time
        self._scanning = False
        self.sort_btn.set_sensitive(True)

        # Stop progress indicators, keep banner visible with summary
        self._progress_spinner.set_spinning(False)
        self._progress_bar_row.set_visible(False)

        total = sum(r["total_bytes"] for r in self._scan_results)
        module_count = sum(1 for r in self._scan_results if r["total_bytes"] > 0)
        time_str = _format_elapsed(elapsed)

        if total > 0:
            self._progress_banner.set_title(
                f"Found {bytes_to_human(total)} in {module_count} "
                f"{'module' if module_count == 1 else 'modules'} "
                f"\u00b7 Scanned in {time_str}"
            )
        else:
            self._progress_banner.set_title(f"Nothing to clean \u00b7 Scanned in {time_str}")

        # Rebuild the view via populate() so items within each category are
        # properly sorted (streaming adds them in arrival order).
        self.populate(self._scan_results)
        return elapsed

    # -- Progressive clean --

    def _on_single_clean_result(self, result: dict) -> None:
        """Handle a single clean result during progressive cleaning."""
        # Update overall clean progress
        self._clean_completed += 1
        if self._clean_total > 0:
            self._progress_bar.set_fraction(self._clean_completed / self._clean_total)
        self._progress_banner.set_title(f"Cleaning {self._clean_completed}/{self._clean_total} modules\u2026")

        plugin_id = result["plugin_id"]
        status = self._clean_status.get(plugin_id)
        if not status:
            return

        spinner, check_img, label = status

        # Stop and hide spinner
        spinner.set_spinning(False)
        spinner.set_visible(False)

        # Show status
        if result["errors"]:
            check_img.set_from_icon_name("dialog-warning-symbolic")
            check_img.add_css_class("warning")
            label.set_label("Error")
        else:
            check_img.set_from_icon_name("emblem-ok-symbolic")
            check_img.add_css_class("success")
            label.set_label(f"Freed {bytes_to_human(result['freed_bytes'])}")

        check_img.set_visible(True)
        label.set_visible(True)

    # -- Checkbox logic --

    def _set_all_entries(self, active: bool) -> None:
        """Select or deselect all entry checkboxes."""
        for check, _ in self._entry_checks:
            check.set_active(active)
        for module_check, _, _ in self._module_checks:
            module_check.handler_block_by_func(self._on_module_toggled)
            module_check.set_active(active)
            module_check.set_inconsistent(False)
            module_check.handler_unblock_by_func(self._on_module_toggled)
        for group_check, _ in self._group_checks:
            group_check.handler_block_by_func(self._on_group_toggled)
            group_check.set_active(active)
            group_check.set_inconsistent(False)
            group_check.handler_unblock_by_func(self._on_group_toggled)
        self._update_summary()

    def _on_group_toggled(self, group_check: Gtk.CheckButton, module_checks: list[Gtk.CheckButton]) -> None:
        """Toggle all module checkboxes when the group checkbox changes."""
        active = group_check.get_active()
        for module_check in module_checks:
            module_check.set_active(active)

    def _on_module_toggled(self, module_check: Gtk.CheckButton, child_checks: list[Gtk.CheckButton]) -> None:
        """Toggle all child checkboxes when the module checkbox changes."""
        active = module_check.get_active()
        for check in child_checks:
            check.set_active(active)
        self._update_group_checks()
        self._update_summary()

    def _on_entry_toggled(self, check: Gtk.CheckButton) -> None:
        """Update module and group checkboxes and summary when an entry is toggled."""
        # Update module-level checks
        for module_check, _, child_checks in self._module_checks:
            all_active = all(c.get_active() for c in child_checks)
            any_active = any(c.get_active() for c in child_checks)
            module_check.handler_block_by_func(self._on_module_toggled)
            module_check.set_active(all_active)
            module_check.set_inconsistent(any_active and not all_active)
            module_check.handler_unblock_by_func(self._on_module_toggled)

        # Update group-level checks
        self._update_group_checks()

        self._update_summary()

    def _update_group_checks(self) -> None:
        """Recompute group checkbox states from their module checks."""
        for group_check, module_checks in self._group_checks:
            all_on = all(c.get_active() and not c.get_inconsistent() for c in module_checks)
            any_on = any(c.get_active() or c.get_inconsistent() for c in module_checks)
            group_check.handler_block_by_func(self._on_group_toggled)
            group_check.set_active(all_on)
            group_check.set_inconsistent(any_on and not all_on)
            group_check.handler_unblock_by_func(self._on_group_toggled)

    def _get_selection_info(self) -> dict:
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

    def _update_summary(self) -> None:
        """Update the summary label based on current selection."""
        info = self._get_selection_info()
        if not info["modules"]:
            self.summary_label.set_label("No items selected")
            self.clean_btn.set_sensitive(False)
            return

        self.clean_btn.set_sensitive(True)
        total_items = info["total_items"]
        parts = [
            bytes_to_human(info["total_size"]),
            f"{total_items:,} item{'s' if total_items != 1 else ''}",
        ]
        module_names = [m["name"] for m in info["modules"]]
        if len(module_names) <= 3:
            parts.append(", ".join(module_names))
        else:
            parts.append(f"{len(module_names)} modules")

        self.summary_label.set_label("  \u00b7  ".join(parts))

    # -- File browser popup --

    def _on_view_leaf_entries(
        self,
        button: Gtk.Button,
        path_str: str,
        items: list[tuple[str, int, str]],
        noun: str = "file",
    ) -> None:
        """Open a popup listing leaf entries (e.g. packages) directly."""
        path = Path(path_str)

        popup = Adw.Window()
        popup.set_default_size(650, 500)
        popup.set_modal(True)
        popup.set_transient_for(self.window)

        toolbar_view = Adw.ToolbarView()
        popup.set_content(toolbar_view)

        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=path.name, subtitle=str(path.parent)))
        toolbar_view.add_top_bar(header)

        self._populate_file_popup(popup, toolbar_view, items, noun=noun)
        popup.present()

    def _on_view_files(self, button: Gtk.Button, path_str: str) -> None:
        """Open a popup window listing all files in the given directory."""
        path = Path(path_str)

        popup = Adw.Window()
        popup.set_default_size(650, 500)
        popup.set_modal(True)
        popup.set_transient_for(self.window)

        toolbar_view = Adw.ToolbarView()
        popup.set_content(toolbar_view)

        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=path.name, subtitle=str(path.parent)))
        toolbar_view.add_top_bar(header)

        spinner = Gtk.Spinner(spinning=True, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        toolbar_view.set_content(spinner)
        popup.present()

        def enumerate_files():
            files: list[tuple[str, int]] = []
            try:
                for item in path.rglob("*"):
                    try:
                        if not item.is_symlink() and item.is_file():
                            try:
                                size = item.lstat().st_size
                            except OSError:
                                size = 0
                            files.append((str(item.relative_to(path)), size))
                    except OSError:
                        pass
            except OSError:
                pass
            files.sort(key=lambda x: x[0])
            GLib.idle_add(self._populate_file_popup, popup, toolbar_view, files)

        threading.Thread(target=enumerate_files, daemon=True).start()

    def _populate_file_popup(
        self,
        popup: Adw.Window,
        toolbar_view: Adw.ToolbarView,
        files: list[tuple[str, int]] | list[tuple[str, int, str]],
        *,
        noun: str = "file",
    ) -> None:
        """Fill the file browser popup with enumerated files."""
        total_size = sum(f[1] for f in files)
        is_leaf = noun != "file"

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        summary = Gtk.Label(
            label=f"{len(files):,} {noun}{'s' if len(files) != 1 else ''}  \u00b7  {bytes_to_human(total_size)}",
            margin_top=8,
            margin_bottom=8,
            margin_start=16,
            margin_end=16,
            halign=Gtk.Align.START,
        )
        summary.add_css_class("dim-label")
        main_box.append(summary)
        main_box.append(Gtk.Separator())

        if not files:
            status = Adw.StatusPage(
                icon_name="folder-open-symbolic",
                title="Empty Directory",
                description="No files found in this directory.",
                vexpand=True,
            )
            main_box.append(status)
        else:
            string_list = Gtk.StringList()
            for f in files:
                desc = f[2] if len(f) > 2 else ""
                string_list.append(f"{f[0]}\t{f[1]}\t{desc}")

            icon_name = "system-software-install-symbolic" if is_leaf else "text-x-generic-symbolic"
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self._on_file_item_setup, icon_name)
            factory.connect("bind", self._on_file_item_bind)

            list_view = Gtk.ListView(
                model=Gtk.NoSelection(model=string_list),
                factory=factory,
            )

            scrolled = Gtk.ScrolledWindow(vexpand=True)
            scrolled.set_child(list_view)
            main_box.append(scrolled)

        toolbar_view.set_content(main_box)

    def _on_file_item_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
        icon_name: str = "text-x-generic-symbolic",
    ) -> None:
        """Create widgets for a file browser list row."""
        box = Gtk.Box(
            spacing=8,
            margin_start=12,
            margin_end=12,
            margin_top=4,
            margin_bottom=4,
        )

        icon = Gtk.Image.new_from_icon_name(icon_name)
        box.append(icon)

        labels_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        path_label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE)
        labels_box.append(path_label)

        desc_label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        desc_label.add_css_class("caption")
        desc_label.add_css_class("dim-label")
        labels_box.append(desc_label)

        box.append(labels_box)

        size_label = Gtk.Label(xalign=1)
        size_label.add_css_class("numeric")
        size_label.add_css_class("dim-label")
        box.append(size_label)

        box._path_label = path_label
        box._desc_label = desc_label
        box._size_label = size_label
        list_item.set_child(box)

    def _on_file_item_bind(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        """Bind file data to a list row."""
        data = list_item.get_item().get_string()
        parts = data.split("\t", 2)
        rel_path, size_str = parts[0], parts[1]
        desc = parts[2] if len(parts) > 2 else ""

        box = list_item.get_child()
        box._path_label.set_label(rel_path)
        box._size_label.set_label(bytes_to_human(int(size_str)))
        box._desc_label.set_label(desc)
        box._desc_label.set_visible(bool(desc))

    # -- Cleaning --

    def _on_clean_clicked(self, button: Gtk.Button) -> None:
        """Execute cleaning of selected items, or navigate to dashboard after clean."""
        if self._clean_done:
            self.window.switch_to_dashboard()
            return

        # Build per-plugin entry lists for the clean operation
        entries_by_plugin: dict[str, list[dict]] = {}
        for check, info in self._entry_checks:
            if not check.get_active():
                continue
            entries_by_plugin.setdefault(info["plugin_id"], []).append(
                {
                    "path": info["path"],
                    "size_bytes": info["size_bytes"],
                }
            )

        if not entries_by_plugin:
            self.window.show_toast("Nothing selected to clean.")
            return

        if not SettingsView.confirm_before_cleaning():
            self._start_clean(entries_by_plugin)
            return

        # Build descriptive dialog from selection info
        sel = self._get_selection_info()
        total_items = sel["total_items"]

        lines = []
        for m in sorted(sel["modules"], key=lambda m: m["size"], reverse=True):
            count = m["item_count"]
            lines.append(
                f"  {m['name']} \u2014 {bytes_to_human(m['size'])} " f"({count} item{'s' if count != 1 else ''})"
            )

        body = "The following will be permanently deleted:\n\n"
        body += "\n".join(lines)
        body += f"\n\nTotal: {bytes_to_human(sel['total_size'])}. This cannot be undone."

        root_names = sorted(m["name"] for m in sel["modules"] if m["requires_root"])
        if root_names:
            body += f"\n\nAdministrator authentication is required for: " f"{', '.join(root_names)}."

        show_confirm_dialog(
            self.window,
            f"Clean {total_items} Selected Item{'s' if total_items != 1 else ''}?",
            body,
            "Clean",
            "clean",
            self._on_confirm_response,
            entries_by_plugin,
        )

    def _on_confirm_response(
        self, dialog: Adw.AlertDialog, response: str, entries_by_plugin: dict[str, list[dict]]
    ) -> None:
        if response != "clean":
            return
        self._start_clean(entries_by_plugin)

    def _start_clean(self, entries_by_plugin: dict[str, list[dict]]) -> None:
        self.clean_btn.set_sensitive(False)
        self.clean_btn.set_label("Cleaning…")
        self._toolbar_revealer.set_reveal_child(False)

        # Overall clean progress
        self._clean_total = len(entries_by_plugin)
        self._clean_completed = 0
        self._progress_banner.set_title(f"Cleaning 0/{self._clean_total} modules\u2026")
        self._progress_bar.set_fraction(0.0)
        self._progress_bar_row.set_visible(True)
        self._progress_spinner.set_spinning(True)
        self._progress_revealer.set_reveal_child(True)

        # Show spinners for plugins being cleaned
        for plugin_id in entries_by_plugin:
            status = self._clean_status.get(plugin_id)
            if status:
                spinner, _, _ = status
                spinner.set_visible(True)
                spinner.set_spinning(True)

        def do_clean():
            results = self.window.client.clean_streaming(
                entries_by_plugin=entries_by_plugin,
                on_result=lambda r: GLib.idle_add(self._on_single_clean_result, r),
            )
            GLib.idle_add(self._on_all_clean_complete, results)

        threading.Thread(target=do_clean, daemon=True).start()

    def _on_all_clean_complete(self, results: list[dict]) -> None:
        self._clean_done = True

        # Stop progress animation, keep banner visible with success summary
        self._progress_spinner.set_spinning(False)
        self._progress_bar_row.set_visible(False)

        total_freed = sum(r["freed_bytes"] for r in results)
        total_errors = sum(len(r["errors"]) for r in results)
        module_count = len(results)
        mod_word = "module" if module_count == 1 else "modules"

        if total_errors > 0:
            err_word = "error" if total_errors == 1 else "errors"
            self._progress_banner.set_title(
                f"Freed {bytes_to_human(total_freed)} from {module_count} {mod_word} " f"with {total_errors} {err_word}"
            )
        else:
            self._progress_banner.set_title(
                f"Freed {bytes_to_human(total_freed)} from " f"{module_count} {mod_word} successfully"
            )

        # Update action bar — swap "Clean Selected" for "Return to Dashboard"
        self.summary_label.set_label(f"{bytes_to_human(total_freed)} freed")
        self.clean_btn.set_label("Return to Dashboard")
        self.clean_btn.set_sensitive(True)
        self.clean_btn.remove_css_class("destructive-action")
        self.clean_btn.add_css_class("suggested-action")
        self._toolbar_revealer.set_reveal_child(False)

        # Disable all checkboxes — the items have been deleted
        for check, _ in self._entry_checks:
            check.set_sensitive(False)
        for check, _, _ in self._module_checks:
            check.set_sensitive(False)
        for check, _ in self._group_checks:
            check.set_sensitive(False)

        self.window.dashboard_view.refresh()
        self.window.modules_view.refresh()


def _common_parent(paths: list[Path]) -> Path:
    """Find the deepest common parent directory for a list of paths."""
    if not paths:
        return Path("/")
    if len(paths) == 1:
        return paths[0].parent

    common = paths[0].parent
    for p in paths[1:]:
        parent = p.parent
        while common != parent and common != Path("/"):
            if str(parent).startswith(str(common)):
                break
            common = common.parent
    return common
