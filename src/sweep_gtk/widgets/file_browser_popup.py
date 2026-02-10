"""File browser popup — browse files/entries inside a scanned directory."""

from __future__ import annotations

import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, GLib, Pango

from sweep.utils import bytes_to_human


def show_file_browser(parent_window: Gtk.Window, path_str: str) -> None:
    """Open a popup window listing all files in the given directory."""
    path = Path(path_str)

    popup = Adw.Window()
    popup.set_default_size(650, 500)
    popup.set_modal(True)
    popup.set_transient_for(parent_window)

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
        GLib.idle_add(_populate_file_popup, popup, toolbar_view, files)

    threading.Thread(target=enumerate_files, daemon=True).start()


def show_leaf_browser(
    parent_window: Gtk.Window,
    path_str: str,
    items: list[tuple[str, int, str]],
    noun: str = "file",
) -> None:
    """Open a popup listing leaf entries (e.g. packages) directly."""
    path = Path(path_str)

    popup = Adw.Window()
    popup.set_default_size(650, 500)
    popup.set_modal(True)
    popup.set_transient_for(parent_window)

    toolbar_view = Adw.ToolbarView()
    popup.set_content(toolbar_view)

    header = Adw.HeaderBar()
    header.set_title_widget(Adw.WindowTitle(title=path.name, subtitle=str(path.parent)))
    toolbar_view.add_top_bar(header)

    _populate_file_popup(popup, toolbar_view, items, noun=noun)
    popup.present()


def _populate_file_popup(
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
        factory.connect("setup", _on_file_item_setup, icon_name)
        factory.connect("bind", _on_file_item_bind)

        list_view = Gtk.ListView(
            model=Gtk.NoSelection(model=string_list),
            factory=factory,
        )

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_child(list_view)
        main_box.append(scrolled)

    toolbar_view.set_content(main_box)


def _on_file_item_setup(
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


def _on_file_item_bind(factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
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
