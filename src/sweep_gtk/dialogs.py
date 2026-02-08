"""Shared dialog helpers for the GTK frontend."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw


def show_confirm_dialog(
    parent: Adw.Window,
    heading: str,
    body: str,
    confirm_label: str,
    confirm_id: str,
    callback,
    *callback_args,
) -> None:
    """Show a destructive confirmation dialog.

    Args:
        parent: The parent window.
        heading: Dialog heading text.
        body: Dialog body text.
        confirm_label: Label for the confirm button.
        confirm_id: Response ID for the confirm action.
        callback: Function called with (dialog, response, *callback_args).
        *callback_args: Extra arguments passed to the callback.
    """
    dialog = Adw.AlertDialog()
    dialog.set_heading(heading)
    dialog.set_body(body)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response(confirm_id, confirm_label)
    dialog.set_response_appearance(confirm_id, Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_default_response("cancel")
    dialog.set_close_response("cancel")
    dialog.connect("response", callback, *callback_args)
    dialog.present(parent)
