"""Main application window."""

from __future__ import annotations

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, GLib

from sweep_gtk.dbus_client import SweepClient
from sweep_gtk.views.dashboard import DashboardView
from sweep_gtk.views.modules_list import ModulesView
from sweep_gtk.views.scan_results import ScanResultsView
from sweep_gtk.views.settings import SettingsView


class SweepWindow(Adw.ApplicationWindow):
    """Main Sweep application window."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_default_size(900, 700)
        self.set_title("Sweep")

        self.client = SweepClient()

        # Toast overlay wraps everything
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(main_box)

        # Header bar with view switcher
        self.header = Adw.HeaderBar()
        self.view_switcher_title = Adw.ViewSwitcherTitle()
        self.header.set_title_widget(self.view_switcher_title)
        main_box.append(self.header)

        # View stack
        self.view_stack = Adw.ViewStack()
        self.view_switcher_title.set_stack(self.view_stack)

        # Bottom view switcher bar (for narrow windows)
        switcher_bar = Adw.ViewSwitcherBar()
        switcher_bar.set_stack(self.view_stack)
        self.view_switcher_title.connect(
            "notify::title-visible",
            lambda obj, _: switcher_bar.set_reveal(obj.get_title_visible()),
        )

        # Create views
        self.dashboard_view = DashboardView(self)
        self.modules_view = ModulesView(self)
        self.scan_results_view = ScanResultsView(self)
        self.settings_view = SettingsView(self)

        # Add views to stack
        self.view_stack.add_titled_with_icon(
            self.dashboard_view, "dashboard", "Dashboard", "user-home-symbolic"
        )
        self.view_stack.add_titled_with_icon(
            self.modules_view, "modules", "Modules", "application-x-addon-symbolic"
        )
        self.view_stack.add_titled_with_icon(
            self.scan_results_view, "results", "Results", "edit-find-symbolic"
        )
        self.view_stack.add_titled_with_icon(
            self.settings_view, "settings", "Settings", "emblem-system-symbolic"
        )

        main_box.append(self.view_stack)
        main_box.append(switcher_bar)

        # Start on dashboard
        self.view_stack.set_visible_child_name("dashboard")

    def show_toast(self, message: str, timeout: int = 3) -> None:
        """Show a toast notification."""
        toast = Adw.Toast(title=message, timeout=timeout)
        self.toast_overlay.add_toast(toast)

    def switch_to_results(self) -> None:
        """Navigate to the scan results view."""
        self.view_stack.set_visible_child_name("results")

    def switch_to_dashboard(self) -> None:
        """Navigate to the dashboard view."""
        self.view_stack.set_visible_child_name("dashboard")

    def launch_scan(self, plugin_ids: list[str]) -> None:
        """Launch a streaming scan on the given plugins and show results.

        Used by the Dashboard for Safe Scan / Full Scan actions.
        """
        if not plugin_ids:
            self.show_toast("No modules to scan.")
            return

        plugin_map = {p["id"]: p for p in self.client.list_plugins()}
        group_info: dict[str, int] = {}
        for pid in plugin_ids:
            g = plugin_map.get(pid, {}).get("group")
            if g:
                group_info[g["id"]] = group_info.get(g["id"], 0) + 1

        results_view = self.scan_results_view
        results_view.begin_streaming_scan(len(plugin_ids), group_info, show_empty=False)
        self.switch_to_results()

        generation = results_view._scan_generation

        def do_scan():
            def on_result(result: dict) -> None:
                GLib.idle_add(results_view.add_streaming_result, result, generation)

            self.client.scan_streaming(plugin_ids=plugin_ids, on_result=on_result)
            GLib.idle_add(self._on_launched_scan_complete)

        threading.Thread(target=do_scan, daemon=True).start()

    def _on_launched_scan_complete(self) -> None:
        """Finalize a scan launched via launch_scan()."""
        from sweep.utils import bytes_to_human, format_elapsed

        results_view = self.scan_results_view
        elapsed = results_view.finish_streaming_scan()

        total = sum(r["total_bytes"] for r in results_view._scan_results)
        time_str = format_elapsed(elapsed)
        if total > 0:
            self.show_toast(f"Found {bytes_to_human(total)} reclaimable space in {time_str}.")
        else:
            self.show_toast(f"Nothing to clean ({time_str}).")
