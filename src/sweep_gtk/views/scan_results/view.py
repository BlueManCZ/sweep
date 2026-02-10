"""Scan results view — preview with selective cleaning."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from sweep.settings import Settings
from sweep.utils import bytes_to_human, format_elapsed as _format_elapsed
from sweep_gtk.constants import CATEGORY_LABELS
from sweep_gtk.widgets import (
    icon_label as _icon_label,
    reveal_in_file_manager,
    show_dirs_browser,
    show_file_browser,
    show_leaf_browser,
)
from sweep_gtk.views.scan_results.helpers import _format_counts, _common_parent
from sweep_gtk.views.scan_results.selection import _SelectionState
from sweep_gtk.views.scan_results.clean_controller import _CleanController

_SORT_KEY = "results.sort_by_size"

if TYPE_CHECKING:
    from sweep_gtk.window import SweepWindow


class ScanResultsView(Gtk.Box):
    """View showing scan results with per-item selection."""

    def __init__(self, window: SweepWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self._scan_results: list[dict] = []
        self._selection = _SelectionState(on_changed=self._update_summary)
        self._clean = _CleanController(self)
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

        # Track expander rows for expanded-state preservation across re-sorts
        # Keys are plugin_id (standalone modules) or group_id (group expanders)
        self._expander_rows: dict[str, Adw.ExpanderRow] = {}
        self._saved_expanded: dict[str, bool] = {}

        # Category-based PreferencesGroups (mirrors Modules view layout)
        self._category_groups: dict[str, Adw.PreferencesGroup] = {}

        # Per-category sorted children for streaming insertion order
        # Maps cat_id -> list of (size_bytes, sort_order, name, widget) tuples
        self._category_children: dict[str, list[tuple[int, int, str, Gtk.Widget]]] = {}

        # Post-clean UI tracking
        self._browse_buttons: list[Gtk.Button] = []
        self._size_labels: list[Gtk.Label] = []
        self._plugin_rows: dict[str, Gtk.Widget] = {}
        self._group_plugin_ids: dict[str, list[str]] = {}
        self._plugin_to_cat: dict[str, str] = {}
        self._nothing_found_group: Adw.PreferencesGroup | None = None

        self._build_progress_ui()
        self._build_toolbar()

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
        self.clean_btn.connect("clicked", self._clean.on_clean_clicked)
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

    def _add_clean_status_widgets(
        self, row: Adw.ActionRow | Adw.ExpanderRow, entity_id: str, *, is_group: bool = False
    ) -> None:
        """Add hidden spinner + checkmark + label for clean progress."""
        spinner = Gtk.Spinner(visible=False, valign=Gtk.Align.CENTER)
        check_img = Gtk.Image(visible=False, valign=Gtk.Align.CENTER)
        label = Gtk.Label(visible=False, valign=Gtk.Align.CENTER)
        label.add_css_class("caption")
        label.add_css_class("dim-label")
        # ExpanderRow stacks suffixes right-to-left; reverse order so
        # the visual result matches ActionRow: [spinner] [✓] [label]
        if isinstance(row, Adw.ExpanderRow):
            row.add_suffix(label)
            row.add_suffix(check_img)
            row.add_suffix(spinner)
        else:
            row.add_suffix(spinner)
            row.add_suffix(check_img)
            row.add_suffix(label)
        if is_group:
            self._clean.register_group(entity_id, spinner, check_img, label)
        else:
            self._clean.register_plugin(entity_id, spinner, check_img, label)

    def _build_progress_ui(self) -> None:
        """Build the progress indicator shared by scan and clean workflows."""
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

    def _build_toolbar(self) -> None:
        """Build the floating toolbar with selection and sort controls."""
        self._toolbar_revealer = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.SLIDE_UP,
            reveal_child=False,
        )
        toolbar = Gtk.Box(spacing=6, margin_start=12, margin_end=12)

        select_all_btn = Gtk.Button(child=_icon_label("edit-select-all-symbolic", "Select All"))
        select_all_btn.connect("clicked", lambda _: self._selection.set_all(True))
        toolbar.append(select_all_btn)

        select_none_btn = Gtk.Button(child=_icon_label("edit-clear-symbolic", "Select None"))
        select_none_btn.connect("clicked", lambda _: self._selection.set_all(False))
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

    def _on_sort_toggled(self, button: Gtk.ToggleButton) -> None:
        """Re-populate the view when sort toggle changes."""
        self._sort_by_size = button.get_active()
        Settings.instance().set(_SORT_KEY, self._sort_by_size)

        if self._scanning:
            # Re-sort existing items in all categories without full rebuild
            for cat_id in self._category_children:
                self._sort_category_items(cat_id)
            return

        # Save expanded state so rows are created already expanded/collapsed
        self._saved_expanded = {key: row.get_expanded() for key, row in self._expander_rows.items()}
        self.populate(self._scan_results)
        self._saved_expanded = {}

    def populate(self, results: list[dict]) -> None:
        """Populate the view with scan results."""
        self._scan_results = results
        self._selection.clear()
        self._expander_rows.clear()
        self._clean.clear()
        self._category_groups.clear()
        self._browse_buttons.clear()
        self._size_labels.clear()
        self._plugin_rows.clear()
        self._group_plugin_ids.clear()
        self._plugin_to_cat.clear()
        self._nothing_found_group = None

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

        for result in results:
            self._plugin_to_cat[result["plugin_id"]] = cat_id

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
        module_row.set_subtitle(_format_counts(total_files, noun, result["file_count"]))
        plugin_id = result["plugin_id"]
        if plugin_id in self._saved_expanded:
            module_row.set_expanded(self._saved_expanded[plugin_id])
        self._expander_rows[plugin_id] = module_row
        self._plugin_rows[plugin_id] = module_row

        module_check = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
        module_row.add_prefix(module_check)

        module_icon = Gtk.Image.new_from_icon_name(result.get("icon", "application-x-executable-symbolic"))
        module_row.add_prefix(module_icon)

        # Size label
        size_label = Gtk.Label(label=bytes_to_human(result["total_bytes"]))
        size_label.add_css_class("numeric")
        size_label.add_css_class("dim-label")
        module_row.add_suffix(size_label)
        self._size_labels.append(size_label)

        self._add_clean_status_widgets(module_row, result["plugin_id"])

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
            elif entry.get("description"):
                row.set_subtitle(entry["description"])

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
                view_btn.connect("clicked", lambda _, p=entry["path"]: show_file_browser(self.window, p))
                row.add_suffix(view_btn)
                self._browse_buttons.append(view_btn)

            # Reveal in File Manager button (skip when Browse files is already shown)
            if not (is_dir and child_count > 0):
                fm_btn = Gtk.Button.new_from_icon_name("folder-open-symbolic")
                fm_btn.add_css_class("flat")
                fm_btn.set_valign(Gtk.Align.CENTER)
                fm_btn.set_tooltip_text("Open in File Manager")
                uri = entry_path.as_uri()
                fm_btn.connect("clicked", lambda _, u=uri: reveal_in_file_manager(u))
                row.add_suffix(fm_btn)
                self._browse_buttons.append(fm_btn)

            # Per-entry checkbox
            check = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
            check.connect("toggled", self._selection.on_entry_toggled)
            row.add_suffix(check)
            row.set_activatable_widget(check)

            child_checks.append(check)
            self._selection.add_entry(
                check,
                {
                    "plugin_id": result["plugin_id"],
                    "plugin_name": result["plugin_name"],
                    "path": entry["path"],
                    "size_bytes": entry["size_bytes"],
                    "requires_root": result.get("requires_root", False),
                },
            )

            module_row.add_row(row)

        # Wire module checkbox to toggle all children
        module_check.connect("toggled", self._selection.on_module_toggled, child_checks)
        self._selection.add_module(module_check, result["plugin_id"], child_checks)

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
        row.set_subtitle(_format_counts(total_files, noun, result["file_count"]))
        row.add_prefix(Gtk.Image.new_from_icon_name(result.get("icon", "application-x-executable-symbolic")))

        self._add_clean_status_widgets(row, result["plugin_id"])

        entry_paths = [Path(e["path"]) for e in result["entries"]]

        # Size label
        size_label = Gtk.Label(label=bytes_to_human(result["total_bytes"]))
        size_label.add_css_class("numeric")
        size_label.add_css_class("dim-label")
        row.add_suffix(size_label)
        self._size_labels.append(size_label)

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
                view_btn.connect(
                    "clicked",
                    lambda _, bp=str(browse_path), li=leaf_items, n=noun: show_leaf_browser(self.window, bp, li, n),
                )
            else:
                # Browse only this plugin's directories, not the entire common parent
                view_btn.connect(
                    "clicked",
                    lambda _, d=list(entry_paths), bp=browse_path, t=result["plugin_name"]: show_dirs_browser(
                        self.window, d, bp, t
                    ),
                )
            row.add_suffix(view_btn)
            self._browse_buttons.append(view_btn)

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
            self._selection.add_entry(
                check,
                {
                    "plugin_id": result["plugin_id"],
                    "plugin_name": result["plugin_name"],
                    "path": entry["path"],
                    "size_bytes": entry["size_bytes"],
                    "requires_root": result.get("requires_root", False),
                },
            )

        # Wire member checkbox to toggle all hidden entry checks
        member_check.connect("toggled", self._selection.on_module_toggled, hidden_checks)
        self._selection.add_module(member_check, result["plugin_id"], hidden_checks)

        self._plugin_rows[result["plugin_id"]] = row
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
        group_row.set_subtitle(_format_counts(group_total_files, "file", group_entry_count))
        if group_id in self._saved_expanded:
            group_row.set_expanded(self._saved_expanded[group_id])
        self._expander_rows[group_id] = group_row

        group_check = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
        group_row.add_prefix(group_check)
        group_row.add_prefix(Gtk.Image.new_from_icon_name(group_icon))

        # Size label
        size_label = Gtk.Label(label=bytes_to_human(group_total_bytes))
        size_label.add_css_class("numeric")
        size_label.add_css_class("dim-label")
        group_row.add_suffix(size_label)
        self._size_labels.append(size_label)

        self._add_clean_status_widgets(group_row, group_id, is_group=True)
        cat_group.add(group_row)

        # Create flat member rows inside the group expander
        member_module_checks: list[Gtk.CheckButton] = []
        for result in member_results:
            member_row, member_check = self._create_group_member_row(result)
            group_row.add_row(member_row)
            member_module_checks.append(member_check)

        self._group_plugin_ids[group_id] = [r["plugin_id"] for r in member_results]

        # Wire group checkbox → all member module checks
        group_check.connect("toggled", self._selection.on_group_toggled, member_module_checks)
        self._selection.add_group(group_check, member_module_checks)

    def _populate_empty_plugins(self, empty_results: list[dict]) -> None:
        """Show plugins that were scanned but found nothing."""
        group = Adw.PreferencesGroup(
            title="Nothing Found",
            description="These modules were scanned but had nothing to clean",
        )
        self.prefs_page.add(group)
        self._groups.append(group)
        self._nothing_found_group = group

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
        self._selection.clear()
        self._clean.clear()
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
        self._browse_buttons.clear()
        self._size_labels.clear()
        self._plugin_rows.clear()
        self._group_plugin_ids.clear()
        self._plugin_to_cat.clear()
        self._nothing_found_group = None

        # Set streaming state
        self._scanning = True
        self._scan_total = total_plugins
        self._scan_completed = 0
        self._scan_generation += 1

        self._clean.reset()

        # Show progress indicator, hide action bar and toolbar
        self._progress_banner.set_title(f"Scanning 0/{total_plugins} modules\u2026")
        self._progress_bar.set_fraction(0.0)
        self._progress_bar_row.set_visible(True)
        self._progress_spinner.set_spinning(True)
        self._progress_revealer.set_reveal_child(True)
        self.action_bar.set_visible(False)
        self._toolbar_revealer.set_reveal_child(False)

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
            # Track metadata for sorted insertion within category
            self._category_children.setdefault(cat_id, []).append(
                (
                    result["total_bytes"],
                    result.get("sort_order", 50),
                    result["plugin_name"].lower(),
                    self._expander_rows[result["plugin_id"]],
                )
            )
            self._sort_category_items(cat_id)
        else:
            return  # standalone empty result — nothing to render yet

        # Re-sort categories on the page
        self._resort_groups()

        # Show action bar and toolbar once we have actionable results
        if self._selection.has_modules:
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

        self._teardown_streaming_group(group_id, cat_id, actionable, result)

        if not actionable:
            return

        cat_group = self._get_or_create_category_group(cat_id)
        remaining = expected - len(pending)
        if self._sort_by_size:
            actionable.sort(key=lambda r: r["total_bytes"], reverse=True)
        else:
            actionable.sort(key=lambda r: (r.get("sort_order", 50), r["plugin_name"].lower()))

        if remaining <= 0:
            self._populate_group_result(actionable, cat_group)
            self._group_widgets[group_id] = (cat_group, self._expander_rows[group["id"]])
        else:
            self._build_partial_group(actionable, group, remaining, cat_group)

        # Track metadata for sorted insertion within category
        group_total = sum(r["total_bytes"] for r in actionable)
        best = actionable[0]
        group_widget = self._group_widgets[group_id][1]
        self._category_children.setdefault(cat_id, []).append(
            (
                group_total,
                best.get("sort_order", 50),
                best["plugin_name"].lower(),
                group_widget,
            )
        )
        self._sort_category_items(cat_id)

    def _teardown_streaming_group(
        self,
        group_id: str,
        cat_id: str,
        actionable: list[dict],
        new_result: dict,
    ) -> None:
        """Remove old group widget and clean up stale selection/clean state."""
        old_entry = self._group_widgets.pop(group_id, None)
        if not old_entry:
            return

        old_cat_group, old_expander = old_entry
        old_cat_group.remove(old_expander)

        # Remove from category children tracking
        if cat_id in self._category_children:
            self._category_children[cat_id] = [
                item for item in self._category_children[cat_id] if item[3] is not old_expander
            ]

        # Clean up checks for previously rendered (non-empty) members
        previously_rendered = {r["plugin_id"] for r in actionable}
        if new_result["total_bytes"] > 0:
            previously_rendered.discard(new_result["plugin_id"])
        self._selection.remove_plugin_ids(previously_rendered)
        self._clean.remove_plugin_ids(previously_rendered)

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
        group_row.set_subtitle(_format_counts(group_total_files, "file", group_entry_count))

        group_check = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
        group_row.add_prefix(group_check)
        group_row.add_prefix(Gtk.Image.new_from_icon_name(group_icon))

        # Size label
        size_label = Gtk.Label(label=bytes_to_human(group_total_bytes))
        size_label.add_css_class("numeric")
        size_label.add_css_class("dim-label")
        group_row.add_suffix(size_label)
        self._size_labels.append(size_label)

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

        group_check.connect("toggled", self._selection.on_group_toggled, member_module_checks)
        self._selection.add_group(group_check, member_module_checks)

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
        """Re-sort items within a category group to maintain correct display order.

        Each entry in _category_children is (size_bytes, sort_order, name, widget).
        """
        children = self._category_children.get(cat_id)
        if not children or len(children) <= 1:
            return
        cat_group = self._category_groups[cat_id]
        for _, _, _, widget in children:
            cat_group.remove(widget)
        if self._sort_by_size:
            children.sort(key=lambda x: (-x[0], x[2]))
        else:
            children.sort(key=lambda x: (x[1], x[2]))
        for _, _, _, widget in children:
            cat_group.add(widget)

    def finish_streaming_scan(self) -> float:
        """Finalize the streaming scan — show summary banner, rebuild with correct ordering.

        Returns:
            Elapsed scan time in seconds.
        """
        elapsed = time.monotonic() - self._scan_start_time
        self._scanning = False

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

    def _update_summary(self) -> None:
        """Update the summary label based on current selection."""
        info = self._selection.get_selection_info()
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
