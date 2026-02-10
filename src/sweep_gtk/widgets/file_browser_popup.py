"""File browser popup — browse files/entries inside a scanned directory."""

from __future__ import annotations

import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk, GLib, Pango

from sweep.utils import bytes_to_human


def reveal_in_file_manager(uri: str) -> None:
    """Reveal a file or directory in the system file manager, selecting it.

    Uses the ``org.freedesktop.FileManager1.ShowItems`` DBus method which
    opens the file manager with the item highlighted.  Falls back to
    ``Gtk.show_uri`` on the containing directory if DBus fails.
    """
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            "org.freedesktop.FileManager1",
            "/org/freedesktop/FileManager1",
            "org.freedesktop.FileManager1",
            "ShowItems",
            GLib.Variant("(ass)", ([uri], "")),
            None,
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )
    except Exception:
        gfile = Gio.File.new_for_uri(uri)
        path = Path(gfile.get_path() or "/")
        target = path if path.is_dir() else path.parent
        Gtk.show_uri(None, target.as_uri(), 0)


def _create_popup(
    parent_window: Gtk.Window,
    title: str,
    subtitle: str,
    folder_path: Path,
) -> tuple[Adw.Window, Adw.ToolbarView]:
    """Create a standard file browser popup with header and Open in File Manager button."""
    popup = Adw.Window()
    popup.set_default_size(650, 500)
    popup.set_modal(True)
    popup.set_transient_for(parent_window)

    toolbar_view = Adw.ToolbarView()
    popup.set_content(toolbar_view)

    header = Adw.HeaderBar()
    header.set_title_widget(Adw.WindowTitle(title=title, subtitle=subtitle))

    open_btn = Gtk.Button.new_from_icon_name("folder-open-symbolic")
    open_btn.add_css_class("flat")
    open_btn.set_tooltip_text("Open in File Manager")
    uri = folder_path.as_uri()
    open_btn.connect("clicked", lambda _, u=uri: Gtk.show_uri(popup, u, 0))
    header.pack_end(open_btn)

    toolbar_view.add_top_bar(header)
    return popup, toolbar_view


def show_file_browser(parent_window: Gtk.Window, path_str: str) -> None:
    """Open a popup window listing all files and directories."""
    path = Path(path_str)
    popup, toolbar_view = _create_popup(parent_window, path.name, str(path), path)

    spinner = Gtk.Spinner(spinning=True, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
    toolbar_view.set_content(spinner)
    popup.present()

    def enumerate_files():
        entries: list[tuple[str, int, bool]] = []
        try:
            for item in path.rglob("*"):
                try:
                    if not item.is_symlink():
                        is_file = item.is_file()
                        is_dir = item.is_dir()
                        if is_file or is_dir:
                            try:
                                size = item.lstat().st_size if is_file else 0
                            except OSError:
                                size = 0
                            entries.append((str(item.relative_to(path)), size, is_dir))
                except OSError:
                    pass
        except OSError:
            pass
        entries.sort(key=lambda x: x[0])
        GLib.idle_add(lambda: _populate_file_popup(popup, toolbar_view, entries, base_path=path))

    threading.Thread(target=enumerate_files, daemon=True).start()


def show_dirs_browser(
    parent_window: Gtk.Window,
    dirs: list[Path],
    base_path: Path,
    title: str,
) -> None:
    """Open a popup listing files from specific directories only.

    Unlike show_file_browser() which scans one directory tree, this only
    enumerates files within the listed directories.  Files are shown relative
    to *base_path* so directory names remain visible.

    Args:
        parent_window: Transient parent window.
        dirs: Specific directories to scan.
        base_path: Common ancestor used for relative path display.
        title: Popup title (e.g. plugin name).
    """
    popup, toolbar_view = _create_popup(parent_window, title, str(base_path), base_path)

    spinner = Gtk.Spinner(spinning=True, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
    toolbar_view.set_content(spinner)
    popup.present()

    def enumerate_files():
        entries: list[tuple[str, int, bool]] = []
        for d in dirs:
            if not d.is_dir():
                continue
            try:
                for item in d.rglob("*"):
                    try:
                        if not item.is_symlink():
                            is_file = item.is_file()
                            is_dir = item.is_dir()
                            if is_file or is_dir:
                                try:
                                    size = item.lstat().st_size if is_file else 0
                                except OSError:
                                    size = 0
                                entries.append((str(item.relative_to(base_path)), size, is_dir))
                    except OSError:
                        pass
            except OSError:
                pass
        entries.sort(key=lambda x: x[0])
        GLib.idle_add(lambda: _populate_file_popup(popup, toolbar_view, entries, base_path=base_path))

    threading.Thread(target=enumerate_files, daemon=True).start()


def show_leaf_browser(
    parent_window: Gtk.Window,
    path_str: str,
    items: list[tuple[str, int, str]],
    noun: str = "file",
) -> None:
    """Open a popup listing leaf entries (e.g. packages) directly."""
    path = Path(path_str)
    popup, toolbar_view = _create_popup(parent_window, path.name, str(path), path)

    _populate_file_popup(popup, toolbar_view, items, noun=noun)
    popup.present()


def _populate_file_popup(
    popup: Adw.Window,
    toolbar_view: Adw.ToolbarView,
    files: list[tuple[str, int]] | list[tuple[str, int, str]] | list[tuple[str, int, bool]],
    *,
    noun: str = "file",
    base_path: Path | None = None,
) -> None:
    """Fill the file browser popup with enumerated files.

    Args:
        base_path: When set, tuples are ``(rel_path, size, is_dir)`` and each
            row gets a folder/file icon plus an *Open in File Manager* button.
            When *None*, tuples are ``(rel_path, size[, desc])`` (leaf listing).
    """
    total_size = sum(f[1] for f in files)
    is_leaf = noun != "file"

    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

    # Build summary — split count into files/folders when applicable
    if base_path is not None:
        dir_count = sum(1 for f in files if len(f) > 2 and f[2] is True)
        file_count = len(files) - dir_count
        parts: list[str] = []
        if file_count:
            parts.append(f"{file_count:,} file{'s' if file_count != 1 else ''}")
        if dir_count:
            parts.append(f"{dir_count:,} folder{'s' if dir_count != 1 else ''}")
        summary_text = f"{'  \u00b7  '.join(parts)}  \u00b7  {bytes_to_human(total_size)}"
    else:
        summary_text = f"{len(files):,} {noun}{'s' if len(files) != 1 else ''}  \u00b7  {bytes_to_human(total_size)}"

    summary = Gtk.Label(
        label=summary_text,
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
        # Encode items into a StringList with 5 tab-separated fields:
        #   rel_path \t size \t desc \t icon \t uri
        string_list = Gtk.StringList()
        leaf_icon = "system-software-install-symbolic"
        for f in files:
            rel_path = f[0]
            size = f[1]
            if base_path is not None:
                is_dir = f[2] if len(f) > 2 else False
                icon = "folder-symbolic" if is_dir else "text-x-generic-symbolic"
                full = base_path / rel_path
                uri = full.as_uri()
                string_list.append(f"{rel_path}\t{size}\t\t{icon}\t{uri}")
            else:
                desc = f[2] if len(f) > 2 else ""
                string_list.append(f"{rel_path}\t{size}\t{desc}\t{leaf_icon}\t")

        icon_name = leaf_icon if is_leaf else "text-x-generic-symbolic"
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

    open_btn = Gtk.Button.new_from_icon_name("folder-open-symbolic")
    open_btn.add_css_class("flat")
    open_btn.set_tooltip_text("Open in File Manager")
    open_btn.set_valign(Gtk.Align.CENTER)
    open_btn.set_visible(False)
    open_btn._uri = ""
    open_btn.connect("clicked", _on_open_in_file_manager)
    box.append(open_btn)

    box._icon = icon
    box._path_label = path_label
    box._desc_label = desc_label
    box._size_label = size_label
    box._open_btn = open_btn
    list_item.set_child(box)


def _on_file_item_bind(factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
    """Bind file data to a list row."""
    data = list_item.get_item().get_string()
    parts = data.split("\t", 4)
    rel_path = parts[0]
    size_str = parts[1]
    desc = parts[2] if len(parts) > 2 else ""
    icon = parts[3] if len(parts) > 3 else ""
    uri = parts[4] if len(parts) > 4 else ""

    box = list_item.get_child()
    box._path_label.set_label(rel_path)
    box._desc_label.set_label(desc)
    box._desc_label.set_visible(bool(desc))

    if icon:
        box._icon.set_from_icon_name(icon)

    # Hide size for directories (they show 0 which is misleading)
    is_dir = icon == "folder-symbolic"
    box._size_label.set_label("" if is_dir else bytes_to_human(int(size_str)))

    box._open_btn.set_visible(bool(uri))
    box._open_btn._uri = uri


def _on_open_in_file_manager(btn: Gtk.Button) -> None:
    """Reveal the item in the system file manager."""
    reveal_in_file_manager(btn._uri)
