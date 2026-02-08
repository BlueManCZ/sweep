"""Modules list view — cleaning module toggles and scan trigger."""

from __future__ import annotations

from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, GLib

from sweep.settings import Settings
from sweep.utils import bytes_to_human, format_elapsed as _format_elapsed
from sweep_gtk.constants import CATEGORY_LABELS
from sweep_gtk.widgets import icon_label as _icon_label

if TYPE_CHECKING:
    from sweep_gtk.window import SweepWindow

_SETTINGS_KEY = "modules.selection"
_SHOW_UNAVAILABLE_KEY = "modules.show_unavailable"


def _plugin_sort_key(plugin: dict) -> tuple[int, int, str]:
    """Sort plugins: available with items first, empty second, unavailable last.

    Within each tier, sort by sort_order (lower first), then alphabetically.
    """
    if not plugin["available"]:
        tier = 2
    elif not plugin.get("has_items", True):
        tier = 1
    else:
        tier = 0
    return tier, plugin.get("sort_order", 50), plugin["name"].lower()


def _group_sort_key(members: list[dict]) -> tuple[int, int, str]:
    """Sort key for a group row based on its best member."""
    best = min(members, key=_plugin_sort_key)
    return _plugin_sort_key(best)


class ModulesView(Gtk.Box):
    """View listing all cleaning modules with toggles."""

    def __init__(self, window: SweepWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self._plugin_rows: dict[str, _PluginRow | _MemberRow] = {}
        self._group_rows: dict[str, _GroupRow] = {}
        self._category_groups: dict[str, Adw.PreferencesGroup] = {}
        self._show_unavailable = Settings.instance().get(_SHOW_UNAVAILABLE_KEY, False)

        # Empty-section toggle state per category
        self._empty_toggle_rows: dict[str, Adw.ActionRow] = {}
        self._empty_collapsed: dict[str, bool] = {}
        self._empty_chevrons: dict[str, Gtk.Image] = {}

        # Floating toolbar
        toolbar = Gtk.Box(spacing=6, margin_start=12, margin_end=12)

        select_all_btn = Gtk.Button(child=_icon_label("edit-select-all-symbolic", "Select All"))
        select_all_btn.connect("clicked", lambda _: self._set_all(True))
        toolbar.append(select_all_btn)

        select_none_btn = Gtk.Button(child=_icon_label("edit-clear-symbolic", "Select None"))
        select_none_btn.connect("clicked", lambda _: self._set_all(False))
        toolbar.append(select_none_btn)

        spacer = Gtk.Box(hexpand=True)
        toolbar.append(spacer)

        show_unavail_btn = Gtk.ToggleButton(
            child=_icon_label("view-reveal-symbolic", "Show Unavailable"),
            active=self._show_unavailable,
        )
        show_unavail_btn.connect("toggled", self._on_show_unavailable_toggled)
        toolbar.append(show_unavail_btn)

        toolbar_clamp = Adw.Clamp(maximum_size=600, child=toolbar,
                                  margin_top=6, margin_bottom=6)

        # Scrolled content
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        self.append(scrolled)

        self.prefs_page = Adw.PreferencesPage()
        scrolled.set_child(self.prefs_page)

        # Build plugin groups by category
        plugins = window.client.list_plugins()
        categories: dict[str, list[dict]] = {}
        for plugin in plugins:
            cat = plugin["category"]
            categories.setdefault(cat, []).append(plugin)

        for cat_id in CATEGORY_LABELS.keys():
            if cat_id not in categories:
                continue
            group = Adw.PreferencesGroup(title=CATEGORY_LABELS.get(cat_id, cat_id))
            self.prefs_page.add(group)
            self._category_groups[cat_id] = group

            cat_plugins = categories[cat_id]

            # Partition into grouped and standalone
            grouped: dict[str, list[dict]] = {}
            standalone: list[dict] = []
            for plugin in cat_plugins:
                g = plugin.get("group")
                if g:
                    grouped.setdefault(g["id"], []).append(plugin)
                else:
                    standalone.append(plugin)

            # Build a list of top-level items with sort keys
            top_items: list[tuple[tuple, str, object]] = []

            for group_id, members in grouped.items():
                members.sort(key=_plugin_sort_key)
                group_meta = members[0]["group"]
                group_row = _GroupRow(group_meta, members, self._save_selection)
                self._group_rows[group_id] = group_row

                for member_row in group_row.member_rows.values():
                    self._plugin_rows[member_row.plugin_id] = member_row

                top_items.append((_group_sort_key(members), "group", group_row))

            for plugin in standalone:
                row = _PluginRow(plugin)
                self._plugin_rows[plugin["id"]] = row
                row.switch.connect("notify::active", lambda *_: self._save_selection())
                top_items.append((_plugin_sort_key(plugin), "standalone", row))

            top_items.sort(key=lambda x: x[0])
            for _, kind, item in top_items:
                group.add(item)

            # Create the empty-section toggle row for this category
            self._create_empty_toggle_row(cat_id)

        # Bottom toolbar (selection controls)
        self.append(toolbar_clamp)

        # Bottom action bar (scan button)
        action_bar = Gtk.ActionBar()
        self.append(action_bar)

        self.scan_btn = Gtk.Button(label="Scan Selected")
        self.scan_btn.add_css_class("suggested-action")
        self.scan_btn.set_sensitive(bool(self.get_selected_plugin_ids()))
        self.scan_btn.connect("clicked", self.on_scan_clicked)
        action_bar.pack_end(self.scan_btn)

        # Restore saved module selection (after scan_btn exists)
        self._restore_selection()

        # Initial ordering and visibility
        self._reorder_rows()

    def refresh(self) -> None:
        """Re-query has_items state for all plugins and update the UI."""
        fresh = self.window.client.list_plugins()
        for plugin_info in fresh:
            pid = plugin_info["id"]
            row = self._plugin_rows.get(pid)
            if row:
                row.update_has_items(plugin_info)
        for group_row in self._group_rows.values():
            group_row.update_subtitle()
        self._reorder_rows()

    def _reorder_rows(self) -> None:
        """Re-sort top-level rows within each category, placing empty ones below the toggle."""
        for cat_id, group in self._category_groups.items():
            # Collect top-level items for this category
            top_level_rows: list[_PluginRow | _GroupRow] = []
            for row in self._plugin_rows.values():
                if isinstance(row, _PluginRow) and row.plugin_info["category"] == cat_id:
                    top_level_rows.append(row)
            for gid, grow in self._group_rows.items():
                if grow.category == cat_id:
                    top_level_rows.append(grow)

            toggle_row = self._empty_toggle_rows.get(cat_id)

            # Remove all top-level rows and the toggle from the group
            for row in top_level_rows:
                group.remove(row)
            if toggle_row:
                group.remove(toggle_row)

            # Sort top-level items
            def sort_key(r):
                if isinstance(r, _GroupRow):
                    return _group_sort_key(list(r.members.values()))
                return _plugin_sort_key(r.plugin_info)

            top_level_rows.sort(key=sort_key)

            # Separate into above-toggle (non-empty) and below-toggle (empty)
            above_rows = []
            empty_rows = []
            for row in top_level_rows:
                if isinstance(row, _GroupRow):
                    if row.is_all_empty():
                        empty_rows.append(row)
                    else:
                        above_rows.append(row)
                else:
                    if row.plugin_info["available"] and not row.plugin_info.get("has_items", True):
                        empty_rows.append(row)
                    else:
                        above_rows.append(row)

            # Re-add: above rows → toggle → empty rows
            for row in above_rows:
                group.add(row)
            if toggle_row:
                group.add(toggle_row)
            for row in empty_rows:
                group.add(row)

            # Update toggle label and visibility
            self._update_empty_toggle_label(cat_id)

        self._apply_visibility()

    def _on_show_unavailable_toggled(self, button: Gtk.ToggleButton) -> None:
        """Toggle visibility of unavailable plugins."""
        self._show_unavailable = button.get_active()
        Settings.instance().set(_SHOW_UNAVAILABLE_KEY, self._show_unavailable)
        self._apply_visibility()

    def _create_empty_toggle_row(self, cat_id: str) -> None:
        """Create a clickable toggle row for collapsing empty plugins in a category."""
        self._empty_collapsed[cat_id] = True

        chevron = Gtk.Image.new_from_icon_name("go-next-symbolic")
        self._empty_chevrons[cat_id] = chevron

        toggle_row = Adw.ActionRow(activatable=True)
        toggle_row.add_css_class("dim-label")
        toggle_row.add_suffix(chevron)
        toggle_row.connect("activated", self._on_empty_toggle_activated, cat_id)

        group = self._category_groups[cat_id]
        group.add(toggle_row)
        self._empty_toggle_rows[cat_id] = toggle_row

    def _on_empty_toggle_activated(self, _row: Adw.ActionRow, cat_id: str) -> None:
        """Toggle the collapsed state of empty plugins in a category."""
        self._empty_collapsed[cat_id] = not self._empty_collapsed[cat_id]
        self._apply_empty_section_visibility(cat_id)

    def _apply_empty_section_visibility(self, cat_id: str) -> None:
        """Show/hide empty rows and update chevron for one category."""
        collapsed = self._empty_collapsed.get(cat_id, True)

        # Rotate chevron: go-next (▸) when collapsed, go-down (▾) when expanded
        chevron = self._empty_chevrons.get(cat_id)
        if chevron:
            chevron.set_from_icon_name(
                "go-down-symbolic" if not collapsed else "go-next-symbolic"
            )

        # Toggle visibility of empty items (standalone rows and all-empty groups)
        for row in self._plugin_rows.values():
            if isinstance(row, _PluginRow) and row.plugin_info["category"] == cat_id:
                if row.plugin_info["available"] and not row.plugin_info.get("has_items", True):
                    row.set_visible(not collapsed)

        for grow in self._group_rows.values():
            if grow.category == cat_id and grow.is_all_empty():
                grow.set_visible(not collapsed)

    def _update_empty_toggle_label(self, cat_id: str) -> None:
        """Update the toggle row title with the count of empty top-level items."""
        toggle_row = self._empty_toggle_rows.get(cat_id)
        if not toggle_row:
            return

        count = 0
        # Count empty standalone plugins
        for row in self._plugin_rows.values():
            if isinstance(row, _PluginRow) and row.plugin_info["category"] == cat_id:
                if row.plugin_info["available"] and not row.plugin_info.get("has_items", True):
                    count += 1
        # Count all-empty groups
        for grow in self._group_rows.values():
            if grow.category == cat_id and grow.is_all_empty():
                count += 1

        if count == 0:
            toggle_row.set_visible(False)
        else:
            label = f"1 empty module" if count == 1 else f"{count} empty modules"
            toggle_row.set_title(label)
            toggle_row.set_visible(True)

    def _apply_visibility(self) -> None:
        """Show/hide unavailable plugin rows, empty sections, and empty category groups."""
        show = self._show_unavailable

        # Track which categories have visible items
        cat_has_visible: dict[str, bool] = {cat: False for cat in self._category_groups}

        # Standalone plugin rows
        for row in self._plugin_rows.values():
            if not isinstance(row, _PluginRow):
                continue
            cat_id = row.plugin_info["category"]
            available = row.plugin_info["available"]
            is_empty = available and not row.plugin_info.get("has_items", True)

            if is_empty:
                collapsed = self._empty_collapsed.get(cat_id, True)
                row.set_visible(not collapsed)
            else:
                row.set_visible(available or show)

            if row.get_visible():
                cat_has_visible[cat_id] = True

        # Group rows
        for grow in self._group_rows.values():
            cat_id = grow.category
            any_available = any(m["available"] for m in grow.members.values())

            if grow.is_all_empty():
                collapsed = self._empty_collapsed.get(cat_id, True)
                grow.set_visible(not collapsed)
            else:
                grow.set_visible(any_available or show)

            # Show/hide unavailable members inside the group
            for member_row in grow.member_rows.values():
                info = member_row.plugin_info
                member_row.switch.set_sensitive(info["available"])
                if not info["available"]:
                    member_row.set_visible(show)

            if grow.get_visible():
                cat_has_visible[cat_id] = True

        # Toggle rows count as visible content
        for cat_id, toggle_row in self._empty_toggle_rows.items():
            if toggle_row.get_visible():
                cat_has_visible[cat_id] = True

        for cat_id, group in self._category_groups.items():
            group.set_visible(cat_has_visible.get(cat_id, False))

    def _restore_selection(self) -> None:
        """Restore module selection from saved settings.

        If no saved selection exists, only enable plugins with risk_level "safe".
        """
        saved = Settings.instance().get(_SETTINGS_KEY)
        if saved is None:
            self._apply_safe_defaults()
            self._sync_all_group_masters()
            return

        saved_set = set(saved)
        for pid, row in self._plugin_rows.items():
            info = row.plugin_info
            if not info["available"]:
                continue
            row.switch.set_active(pid in saved_set)

        self._sync_all_group_masters()

    def _apply_safe_defaults(self) -> None:
        """Enable only safe-risk plugins that have items when no saved selection exists."""
        for row in self._plugin_rows.values():
            info = row.plugin_info
            if not info["available"]:
                continue
            safe = info["risk_level"] == "safe"
            has = info.get("has_items", True)
            row.switch.set_active(safe and has)

    def _sync_all_group_masters(self) -> None:
        """Sync all group master switches from their members."""
        for grow in self._group_rows.values():
            grow.sync_master_from_members()

    def _save_selection(self) -> None:
        """Persist current module selection to settings."""
        selected = self.get_selected_plugin_ids()
        Settings.instance().set(_SETTINGS_KEY, selected)
        self.scan_btn.set_sensitive(bool(selected))

    def _set_all(self, enabled: bool) -> None:
        """Toggle all plugin switches."""
        for row in self._plugin_rows.values():
            info = row.plugin_info
            if info["available"]:
                row.switch.set_active(enabled)
        for grow in self._group_rows.values():
            grow.sync_master_from_members()
        self._save_selection()

    def get_selected_plugin_ids(self) -> list[str]:
        """Return IDs of selected plugins."""
        return [
            pid for pid, row in self._plugin_rows.items()
            if row.switch.get_active() and row.plugin_info["available"]
        ]

    def on_scan_clicked(self, button: Gtk.Button | None) -> None:
        """Run a streaming scan on selected plugins."""
        selected = self.get_selected_plugin_ids()
        if not selected:
            self.window.show_toast("No modules selected for scanning.")
            return

        self.scan_btn.set_sensitive(False)
        self.scan_btn.set_label("Scanning...")

        # Compute group info: group_id -> count of selected members in that group
        plugins = self.window.client.list_plugins()
        plugin_map = {p["id"]: p for p in plugins}
        group_info: dict[str, int] = {}
        for pid in selected:
            info = plugin_map.get(pid, {})
            g = info.get("group")
            if g:
                group_info[g["id"]] = group_info.get(g["id"], 0) + 1

        # Begin streaming on the results view and switch immediately
        results_view = self.window.scan_results_view
        results_view.begin_streaming_scan(len(selected), group_info)
        self.window.switch_to_results()

        generation = results_view._scan_generation

        def do_scan():
            def on_result(result: dict):
                GLib.idle_add(results_view.add_streaming_result, result, generation)

            self.window.client.scan_streaming(
                plugin_ids=selected,
                on_result=on_result,
            )
            GLib.idle_add(self._on_scan_complete_streaming)

        import threading
        threading.Thread(target=do_scan, daemon=True).start()

    def _on_scan_complete_streaming(self) -> None:
        """Handle streaming scan completion."""
        self.scan_btn.set_sensitive(bool(self.get_selected_plugin_ids()))
        self.scan_btn.set_label("Scan Selected")

        results_view = self.window.scan_results_view
        elapsed = results_view.finish_streaming_scan()

        total = sum(r["total_bytes"] for r in results_view._scan_results)
        time_str = _format_elapsed(elapsed)
        if total > 0:
            self.window.show_toast(
                f"Found {bytes_to_human(total)} reclaimable space in {time_str}.",
            )
        else:
            self.window.show_toast(f"Nothing to clean ({time_str}).")


class _MemberRow(Adw.ActionRow):
    """A member plugin row inside a _GroupRow."""

    def __init__(self, plugin_info: dict) -> None:
        super().__init__()
        self.plugin_info = plugin_info
        self.plugin_id = plugin_info["id"]
        self._has_items = plugin_info.get("has_items", True)

        self.set_title(plugin_info["name"])
        self.set_subtitle(plugin_info["description"])
        self.add_prefix(
            Gtk.Image.new_from_icon_name(plugin_info.get("icon", "application-x-executable-symbolic"))
        )

        # Status badge (before switch so switches stay aligned)
        self._status_label = Gtk.Label()
        self._status_label.add_css_class("caption")
        self._status_label.add_css_class("dim-label")
        self.add_suffix(self._status_label)

        # Info icon for unavailable reason (tooltip on hover)
        self._info_icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
        self._info_icon.set_tooltip_text("")
        self._info_icon.add_css_class("dim-label")
        self.add_suffix(self._info_icon)

        # Switch (always last suffix for vertical alignment)
        self.switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.switch.set_active(plugin_info["available"])
        self.switch.set_sensitive(plugin_info["available"])
        self.add_suffix(self.switch)
        self.set_activatable_widget(self.switch)

        self._apply_status_style()

    def _apply_status_style(self) -> None:
        available = self.plugin_info["available"]
        if not available:
            self._status_label.set_label("Not Supported")
            self._status_label.set_visible(True)
            reason = self.plugin_info.get("unavailable_reason")
            self._info_icon.set_visible(bool(reason))
            self._info_icon.set_tooltip_text(reason or "")
            self.add_css_class("dim-label")
        elif not self._has_items:
            self._status_label.set_label("Empty")
            self._status_label.set_visible(True)
            self._info_icon.set_visible(False)
            self.add_css_class("dim-label")
        else:
            self._status_label.set_visible(False)
            self._info_icon.set_visible(False)
            self.remove_css_class("dim-label")

    def update_has_items(self, plugin_info: dict) -> None:
        self._has_items = plugin_info.get("has_items", True)
        self.plugin_info["has_items"] = self._has_items
        self._apply_status_style()


class _GroupRow(Adw.ExpanderRow):
    """A visual group container for related plugins with a master switch."""

    def __init__(self, group_meta: dict, members_data: list[dict], save_cb) -> None:
        super().__init__()
        self._save_cb = save_cb
        self._updating_master = False

        # Store group metadata
        self.group_id = group_meta["id"]
        self.group_name = group_meta["name"]
        self._description = group_meta.get("description", "")
        self.category = members_data[0]["category"]
        self.members: dict[str, dict] = {m["id"]: m for m in members_data}

        self.set_title(group_meta["name"])

        # Use the first member's icon
        first_icon = members_data[0].get("icon", "application-x-executable-symbolic")
        self.add_prefix(Gtk.Image.new_from_icon_name(first_icon))

        # Master switch
        self.master_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.master_switch.connect("notify::active", self._on_master_toggled)
        self.add_action(self.master_switch)

        # Member rows
        self.member_rows: dict[str, _MemberRow] = {}
        for m in members_data:
            member_row = _MemberRow(m)
            member_row.switch.connect("notify::active", self._on_member_toggled)
            self.member_rows[m["id"]] = member_row
            self.add_row(member_row)

        # Aggregated details row (highest risk + requires root)
        details_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=8,
            margin_bottom=8,
            margin_start=16,
        )

        risk_order = {"safe": 0, "moderate": 1, "aggressive": 2}
        highest_risk = max(
            (m["risk_level"] for m in members_data),
            key=lambda r: risk_order.get(r, 0),
        )
        risk_label = Gtk.Label(label=highest_risk.capitalize())
        risk_label.add_css_class("caption")
        if highest_risk == "aggressive":
            risk_label.add_css_class("error")
        elif highest_risk == "moderate":
            risk_label.add_css_class("warning")
        else:
            risk_label.add_css_class("success")
        details_box.append(risk_label)

        if any(m["requires_root"] for m in members_data):
            root_label = Gtk.Label(label="Requires Root")
            root_label.add_css_class("caption")
            root_label.add_css_class("warning")
            details_box.append(root_label)

        details_row = Adw.ActionRow()
        details_row.set_child(details_box)
        self.add_row(details_row)

        self.update_subtitle()

    def update_subtitle(self) -> None:
        """Update subtitle with group description."""
        self.set_subtitle(self._description)

    def is_all_empty(self) -> bool:
        """True if all available members have no items (but at least one is available)."""
        available_members = [m for m in self.members.values() if m["available"]]
        if not available_members:
            return False
        return all(not m.get("has_items", True) for m in available_members)

    def _on_master_toggled(self, switch: Gtk.Switch, _pspec) -> None:
        """Master switch toggled → set all available members."""
        if self._updating_master:
            return
        active = switch.get_active()
        for member_row in self.member_rows.values():
            if member_row.plugin_info["available"]:
                member_row.switch.handler_block_by_func(self._on_member_toggled)
                member_row.switch.set_active(active)
                member_row.switch.handler_unblock_by_func(self._on_member_toggled)
        self._save_cb()

    def _on_member_toggled(self, switch: Gtk.Switch, _pspec) -> None:
        """Any member toggled → recompute master state."""
        self.sync_master_from_members()
        self._save_cb()

    def sync_master_from_members(self) -> None:
        """Set master switch based on member states (no signal recursion)."""
        active_members = [
            r for r in self.member_rows.values()
            if r.plugin_info["available"]
        ]
        if not active_members:
            return

        any_on = any(r.switch.get_active() for r in active_members)
        self._updating_master = True
        self.master_switch.set_active(any_on)
        self._updating_master = False


class _PluginRow(Adw.ExpanderRow):
    """A standalone plugin row with toggle switch and details."""

    def __init__(self, plugin_info: dict) -> None:
        super().__init__()
        self.plugin_info = plugin_info
        self._has_items = plugin_info.get("has_items", True)

        self.set_title(plugin_info["name"])
        self.set_subtitle(plugin_info["description"])
        self.add_prefix(
            Gtk.Image.new_from_icon_name(plugin_info.get("icon", "application-x-executable-symbolic"))
        )

        # Enable switch
        self.switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.switch.set_active(plugin_info["available"])
        self.switch.set_sensitive(plugin_info["available"])
        self.add_action(self.switch)

        # Badges in expanded area
        details_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=8,
            margin_bottom=8,
            margin_start=16,
        )

        # Risk level badge
        risk = plugin_info["risk_level"]
        risk_label = Gtk.Label(label=risk.capitalize())
        risk_label.add_css_class("caption")
        if risk == "aggressive":
            risk_label.add_css_class("error")
        elif risk == "moderate":
            risk_label.add_css_class("warning")
        else:
            risk_label.add_css_class("success")
        details_box.append(risk_label)

        # Requires root badge
        if plugin_info["requires_root"]:
            root_label = Gtk.Label(label="Requires Root")
            root_label.add_css_class("caption")
            root_label.add_css_class("warning")
            details_box.append(root_label)

        # Availability / emptiness indicators
        self._empty_label: Gtk.Label | None = None
        if not plugin_info["available"]:
            reason = plugin_info.get("unavailable_reason")
            text = f"Not Supported: {reason}" if reason else "Not Supported"
            reason_label = Gtk.Label(label=text, wrap=True, xalign=0)
            reason_label.add_css_class("caption")
            reason_label.add_css_class("dim-label")
            details_box.append(reason_label)
        else:
            self._empty_label = Gtk.Label(label="Empty")
            self._empty_label.add_css_class("caption")
            self._empty_label.add_css_class("dim-label")
            self.add_suffix(self._empty_label)
            self._apply_empty_style()

        row = Adw.ActionRow()
        row.set_child(details_box)
        self.add_row(row)

    def _apply_empty_style(self) -> None:
        """Show or hide the empty badge and dim styling based on _has_items."""
        if self._empty_label is None:
            return
        self._empty_label.set_visible(not self._has_items)
        if self._has_items:
            self.remove_css_class("dim-label")
        else:
            self.add_css_class("dim-label")

    def update_has_items(self, plugin_info: dict) -> None:
        """Refresh the has_items state from fresh plugin data."""
        self._has_items = plugin_info.get("has_items", True)
        self.plugin_info["has_items"] = self._has_items
        self._apply_empty_style()
