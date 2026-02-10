"""Manages the clean workflow: confirmation dialog, progress, and completion."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, GLib

from sweep.utils import bytes_to_human
from sweep_gtk.dialogs import show_confirm_dialog
from sweep_gtk.views.settings import SettingsView

if TYPE_CHECKING:
    from sweep_gtk.views.scan_results.view import ScanResultsView


class _CleanController:
    """Manages the clean workflow: confirmation dialog, progress, and completion.

    Owns per-plugin status widgets and clean progress tracking.
    Needs a reference to the parent *ScanResultsView* to access
    shared progress widgets, the window, and the selection state.
    """

    def __init__(self, view: ScanResultsView) -> None:
        self._view = view
        self._clean_status: dict[str, tuple[Gtk.Spinner, Gtk.Image, Gtk.Label]] = {}
        self._clean_total: int = 0
        self._clean_completed: int = 0
        self._clean_done: bool = False
        self._group_clean_status: dict[str, tuple[Gtk.Spinner, Gtk.Image, Gtk.Label]] = {}
        self._plugin_to_group: dict[str, str] = {}
        self._group_clean_tracking: dict[str, dict] = {}
        self._plugin_names: dict[str, str] = {}

    @property
    def is_done(self) -> bool:
        return self._clean_done

    def clear(self) -> None:
        self._clean_status.clear()
        self._group_clean_status.clear()

    def register_plugin(self, plugin_id: str, spinner: Gtk.Spinner, check_img: Gtk.Image, label: Gtk.Label) -> None:
        self._clean_status[plugin_id] = (spinner, check_img, label)

    def register_group(self, group_id: str, spinner: Gtk.Spinner, check_img: Gtk.Image, label: Gtk.Label) -> None:
        self._group_clean_status[group_id] = (spinner, check_img, label)

    def remove_plugin_ids(self, plugin_ids: set[str]) -> None:
        for pid in plugin_ids:
            self._clean_status.pop(pid, None)

    def reset(self) -> None:
        """Reset clean-done state and button styling for a new scan."""
        self._clean_done = False
        self._view.clean_btn.set_label("Clean Selected")
        self._view.clean_btn.remove_css_class("suggested-action")
        self._view.clean_btn.add_css_class("destructive-action")

    # -- Event handlers --

    def on_clean_clicked(self, button: Gtk.Button) -> None:
        """Execute cleaning of selected items, or navigate to dashboard after clean."""
        view = self._view
        if self._clean_done:
            view.window.switch_to_dashboard()
            return

        entries_by_plugin = view._selection.get_entries_by_plugin()

        if not entries_by_plugin:
            view.window.show_toast("Nothing selected to clean.")
            return

        if not SettingsView.confirm_before_cleaning():
            self._start_clean(entries_by_plugin)
            return

        # Build descriptive dialog from selection info
        sel = view._selection.get_selection_info()
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
            view.window,
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
        view = self._view
        view.clean_btn.set_sensitive(False)
        view.clean_btn.set_label("Cleaning\u2026")
        view._toolbar_revealer.set_reveal_child(False)

        # Hide rows not being cleaned
        for plugin_id, row in view._plugin_rows.items():
            if plugin_id not in entries_by_plugin:
                row.set_visible(False)

        # Hide group expanders where no members are being cleaned
        for group_id, member_ids in view._group_plugin_ids.items():
            if not any(pid in entries_by_plugin for pid in member_ids):
                expander = view._expander_rows.get(group_id)
                if expander:
                    expander.set_visible(False)

        # Hide category groups with nothing being cleaned
        cleaned_cats = {view._plugin_to_cat[pid] for pid in entries_by_plugin if pid in view._plugin_to_cat}
        for cat_id, cat_group in view._category_groups.items():
            if cat_id not in cleaned_cats:
                cat_group.set_visible(False)

        # Hide the "Nothing Found" group
        if view._nothing_found_group:
            view._nothing_found_group.set_visible(False)

        # Overall clean progress
        self._clean_total = len(entries_by_plugin)
        self._clean_completed = 0
        view._progress_banner.set_title(f"Cleaning 0/{self._clean_total} modules\u2026")
        view._progress_bar.set_fraction(0.0)
        view._progress_bar_row.set_visible(True)
        view._progress_spinner.set_spinning(True)
        view._progress_revealer.set_reveal_child(True)

        # Show spinners for plugins being cleaned
        for plugin_id in entries_by_plugin:
            status = self._clean_status.get(plugin_id)
            if status:
                spinner, _, _ = status
                spinner.set_visible(True)
                spinner.set_spinning(True)

        # Initialize group-level tracking
        self._plugin_names = {r["plugin_id"]: r["plugin_name"] for r in view._scan_results}
        self._plugin_to_group.clear()
        self._group_clean_tracking.clear()
        for group_id, member_ids in view._group_plugin_ids.items():
            members_cleaning = [pid for pid in member_ids if pid in entries_by_plugin]
            if not members_cleaning:
                continue
            for pid in member_ids:
                self._plugin_to_group[pid] = group_id
            self._group_clean_tracking[group_id] = {
                "expected": len(members_cleaning),
                "completed": 0,
                "freed_bytes": 0,
                "errors": 0,
                "members": [],
            }
            status = self._group_clean_status.get(group_id)
            if status:
                spinner, _, _ = status
                spinner.set_visible(True)
                spinner.set_spinning(True)

        def do_clean():
            results = view.window.client.clean_streaming(
                entries_by_plugin=entries_by_plugin,
                on_result=lambda r: GLib.idle_add(self._on_single_clean_result, r),
            )
            GLib.idle_add(self._on_all_clean_complete, results)

        threading.Thread(target=do_clean, daemon=True).start()

    def _on_single_clean_result(self, result: dict) -> None:
        """Handle a single clean result during progressive cleaning."""
        view = self._view
        self._clean_completed += 1
        if self._clean_total > 0:
            view._progress_bar.set_fraction(self._clean_completed / self._clean_total)
        view._progress_banner.set_title(f"Cleaning {self._clean_completed}/{self._clean_total} modules\u2026")

        plugin_id = result["plugin_id"]
        status = self._clean_status.get(plugin_id)
        if status:
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

        # Update group-level aggregated status
        group_id = self._plugin_to_group.get(plugin_id)
        if group_id:
            tracking = self._group_clean_tracking.get(group_id)
            if tracking:
                tracking["completed"] += 1
                tracking["freed_bytes"] += result["freed_bytes"]
                tracking["errors"] += len(result["errors"])
                tracking["members"].append(
                    {
                        "name": self._plugin_names.get(plugin_id, plugin_id),
                        "freed_bytes": result["freed_bytes"],
                    }
                )
                if tracking["completed"] >= tracking["expected"]:
                    self._finalize_group_clean(group_id, tracking)

    def _finalize_group_clean(self, group_id: str, tracking: dict) -> None:
        """Show aggregated clean status on the group expander row."""
        status = self._group_clean_status.get(group_id)
        if not status:
            return

        spinner, check_img, label = status
        spinner.set_spinning(False)
        spinner.set_visible(False)

        if tracking["errors"] > 0:
            check_img.set_from_icon_name("dialog-warning-symbolic")
            check_img.add_css_class("warning")
        else:
            check_img.set_from_icon_name("emblem-ok-symbolic")
            check_img.add_css_class("success")
        label.set_label(f"Freed {bytes_to_human(tracking['freed_bytes'])}")

        check_img.set_visible(True)
        label.set_visible(True)

        # Update subtitle with cleaned member summary
        expander = self._view._expander_rows.get(group_id)
        if expander:
            parts = [f"{m['name']} \u2014 {bytes_to_human(m['freed_bytes'])}" for m in tracking["members"]]
            expander.set_subtitle(", ".join(parts))

    def _on_all_clean_complete(self, results: list[dict]) -> None:
        view = self._view
        self._clean_done = True

        # Stop progress animation, keep banner visible with success summary
        view._progress_spinner.set_spinning(False)
        view._progress_bar_row.set_visible(False)

        total_freed = sum(r["freed_bytes"] for r in results)
        total_errors = sum(len(r["errors"]) for r in results)
        module_count = len(results)
        mod_word = "module" if module_count == 1 else "modules"

        if total_errors > 0:
            err_word = "error" if total_errors == 1 else "errors"
            view._progress_banner.set_title(
                f"Freed {bytes_to_human(total_freed)} from {module_count} {mod_word} " f"with {total_errors} {err_word}"
            )
        else:
            view._progress_banner.set_title(
                f"Freed {bytes_to_human(total_freed)} from " f"{module_count} {mod_word} successfully"
            )

        # Update action bar — swap "Clean Selected" for "Return to Dashboard"
        view.summary_label.set_label(f"{bytes_to_human(total_freed)} freed")
        view.clean_btn.set_label("Return to Dashboard")
        view.clean_btn.set_sensitive(True)
        view.clean_btn.remove_css_class("destructive-action")
        view.clean_btn.add_css_class("suggested-action")
        view._toolbar_revealer.set_reveal_child(False)

        # Post-clean UI cleanup — collapse, hide checkboxes and browse buttons
        for expander in view._expander_rows.values():
            if expander.get_visible():
                expander.set_expanded(False)
        view._selection.hide_all()
        for btn in view._browse_buttons:
            btn.set_visible(False)
        for icon in view._info_icons:
            icon.set_visible(False)
        for lbl in view._size_labels:
            lbl.set_visible(False)

        view.window.dashboard_view.refresh()
        view.window.modules_view.refresh()
