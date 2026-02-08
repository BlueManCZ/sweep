"""Animated space freed indicator widget."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, GLib

from sweep.utils import bytes_to_human


class SpaceIndicator(Gtk.Box):
    """Animated counter showing bytes freed with a counting-up effect."""

    def __init__(self) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            halign=Gtk.Align.CENTER,
        )
        self._target_bytes = 0
        self._current_bytes = 0
        self._animation_id: int | None = None

        self.value_label = Gtk.Label(label="0 B")
        self.value_label.add_css_class("title-1")
        self.append(self.value_label)

        self.subtitle_label = Gtk.Label(label="Space Freed")
        self.subtitle_label.add_css_class("dim-label")
        self.append(self.subtitle_label)

    def set_bytes(self, total_bytes: int, animate: bool = True) -> None:
        """Set the displayed byte count, optionally with animation."""
        self._target_bytes = total_bytes

        if not animate or total_bytes == 0:
            self._current_bytes = total_bytes
            self.value_label.set_label(bytes_to_human(total_bytes))
            return

        if self._animation_id is not None:
            GLib.source_remove(self._animation_id)

        self._current_bytes = 0
        self._animation_id = GLib.timeout_add(16, self._tick)

    def _tick(self) -> bool:
        """Animation frame — increment towards target."""
        remaining = self._target_bytes - self._current_bytes
        if remaining <= 0:
            self._current_bytes = self._target_bytes
            self.value_label.set_label(bytes_to_human(self._target_bytes))
            self._animation_id = None
            return False

        # Ease out — larger steps at start, smaller near end
        step = max(1, remaining // 10)
        self._current_bytes += step
        self.value_label.set_label(bytes_to_human(self._current_bytes))
        return True
