"""Sweep GTK Application."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio

from sweep_gtk.window import SweepWindow

APP_ID = "io.github.BlueManCZ.sweep"


class SweepApplication(Adw.Application):
    """Main application class."""

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self) -> None:
        win = self.props.active_window
        if not win:
            win = SweepWindow(application=self)
        win.present()


def main() -> None:
    app = SweepApplication()
    app.run(sys.argv)
