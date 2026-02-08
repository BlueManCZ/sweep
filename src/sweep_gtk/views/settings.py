"""Settings view — preferences, plugin paths, history management."""

from __future__ import annotations

from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from sweep import __version__
from sweep.settings import Settings
from sweep_gtk.dialogs import show_confirm_dialog

if TYPE_CHECKING:
    from sweep_gtk.window import SweepWindow

_CONFIRM_KEY = "general.confirm_before_cleaning"


class SettingsView(Adw.PreferencesPage):
    """Application settings and preferences."""

    def __init__(self, window: SweepWindow) -> None:
        super().__init__()
        self.window = window

        # ── General ──────────────────────────────────────────────────
        general_group = Adw.PreferencesGroup(
            title="General",
            description="Application behavior settings",
        )
        self.add(general_group)

        # Confirm before cleaning
        self.confirm_row = Adw.SwitchRow(
            title="Confirm Before Cleaning",
            subtitle="When disabled, cleaning starts immediately without confirmation",
        )
        self._confirm_toggling = False
        self.confirm_row.set_active(Settings.instance().get(_CONFIRM_KEY, True))
        self.confirm_row.connect("notify::active", self._on_confirm_toggled)
        general_group.add(self.confirm_row)

        # ── Plugin Directories ───────────────────────────────────────
        plugins_group = Adw.PreferencesGroup(
            title="Plugin Directories",
            description="Additional paths to search for cleaning plugins",
        )
        self.add(plugins_group)

        system_row = Adw.ActionRow(
            title="System Plugins",
            subtitle="/usr/share/sweep/plugins/",
        )
        system_row.add_suffix(
            Gtk.Image(icon_name="folder-symbolic", css_classes=["dim-label"])
        )
        plugins_group.add(system_row)

        user_row = Adw.ActionRow(
            title="User Plugins",
            subtitle="~/.local/share/sweep/plugins/",
        )
        user_row.add_suffix(
            Gtk.Image(icon_name="folder-symbolic", css_classes=["dim-label"])
        )
        plugins_group.add(user_row)

        # ── History ──────────────────────────────────────────────────
        history_group = Adw.PreferencesGroup(
            title="History",
            description="Cleaning session history management",
        )
        self.add(history_group)

        clear_history_row = Adw.ActionRow(
            title="Clear History",
            subtitle="Remove all recorded cleaning statistics",
        )
        clear_btn = Gtk.Button(
            label="Clear",
            valign=Gtk.Align.CENTER,
            css_classes=["destructive-action"],
        )
        clear_btn.connect("clicked", self._on_clear_history)
        clear_history_row.add_suffix(clear_btn)
        clear_history_row.set_activatable_widget(clear_btn)
        history_group.add(clear_history_row)

        # ── About ────────────────────────────────────────────────────
        about_group = Adw.PreferencesGroup(title="About")
        self.add(about_group)

        version_row = Adw.ActionRow(
            title="Sweep",
            subtitle=f"Version {__version__}",
        )
        version_row.add_suffix(
            Gtk.Image(icon_name="help-about-symbolic", css_classes=["dim-label"])
        )
        about_group.add(version_row)

        license_row = Adw.ActionRow(
            title="License",
            subtitle="GPL-3.0",
        )
        about_group.add(license_row)

    def _on_confirm_toggled(self, row: Adw.SwitchRow, _pspec) -> None:
        if self._confirm_toggling:
            return

        if row.get_active():
            Settings.instance().set(_CONFIRM_KEY, True)
            return

        # Disabling — warn the user first
        show_confirm_dialog(
            self.window,
            "Disable Confirmation?",
            "Files will be deleted immediately when you press Clean, "
            "without any confirmation dialog.\n\n"
            "You can re-enable this at any time in Settings.",
            "Disable",
            "disable",
            self._on_disable_confirm_response,
        )

    def _on_disable_confirm_response(
        self, dialog: Adw.AlertDialog, response: str
    ) -> None:
        if response == "disable":
            Settings.instance().set(_CONFIRM_KEY, False)
        else:
            # User cancelled — revert the switch without re-triggering the handler
            self._confirm_toggling = True
            self.confirm_row.set_active(True)
            self._confirm_toggling = False

    @staticmethod
    def confirm_before_cleaning() -> bool:
        """Whether the user wants a confirmation dialog before cleaning."""
        return Settings.instance().get(_CONFIRM_KEY, True)

    def _on_clear_history(self, button: Gtk.Button) -> None:
        """Clear all cleaning history."""
        show_confirm_dialog(
            self.window,
            "Clear History?",
            "This will permanently remove all cleaning statistics. This cannot be undone.",
            "Clear History",
            "clear",
            self._on_clear_confirmed,
        )

    def _on_clear_confirmed(self, dialog: Adw.AlertDialog, response: str) -> None:
        if response != "clear":
            return
        from sweep.storage import save_history
        save_history({"sessions": []})
        self.window.dashboard_view.refresh()
        self.window.show_toast("History cleared.")
