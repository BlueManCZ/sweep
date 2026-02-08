"""Common widget helpers."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk


def icon_label(icon_name: str, label: str) -> Gtk.Box:
    """Create a Box with an icon and label for use as a button child."""
    box = Gtk.Box(spacing=6)
    box.append(Gtk.Image.new_from_icon_name(icon_name))
    box.append(Gtk.Label(label=label))
    return box
