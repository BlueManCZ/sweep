# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Sweep GTK application."""

import re

import sweep.plugins as _plugins_pkg
import pkgutil

# Auto-discover all built-in plugin modules
plugin_hiddenimports = [
    f"sweep.plugins.{mod.name}"
    for mod in pkgutil.iter_modules(_plugins_pkg.__path__)
]

a = Analysis(
    ["src/sweep_gtk/__main__.py"],
    pathex=["src"],
    datas=[
        ("data/io.github.BlueManCZ.sweep.svg", "data"),
    ],
    hiddenimports=[
        *plugin_hiddenimports,
        "sweep_gtk",
        "sweep_gtk.app",
        "sweep_gtk.window",
        "sweep_gtk.views",
        "sweep_gtk.views.dashboard",
        "sweep_gtk.views.modules_list",
        "sweep_gtk.views.scan_results",
        "sweep_gtk.views.settings",
        "sweep_gtk.widgets",
        "sweep_gtk.widgets.space_indicator",
        "sweep_gtk.dialogs",
        "sweep_gtk.dbus_client",
        "sweep_gtk.constants",
    ],
    excludes=[
        # System packages that cannot be properly bundled — plugins
        # detect their absence at runtime and gracefully degrade.
        "portage",
        "gentoolkit",
        "_emerge",
    ],
    noarchive=False,
)

# ---------------------------------------------------------------------------
# Strip bloat: icon themes, GTK themes, locales, cursors, and unnecessary
# shared libraries.  The target system provides all of these if it has
# GTK4 + libadwaita installed.
# ---------------------------------------------------------------------------

_EXCLUDE_DATA_RE = re.compile(r"|".join([
    r"share/icons/",        # all icon themes (Adwaita, Breeze, Papirus, …)
    r"share/themes/",       # all GTK themes
    r"share/locale/",       # translations
    r"share/mime/",         # MIME database
]))

_EXCLUDE_BIN_RE = re.compile(r"|".join([
    r"libgtk-3\.",          # GTK3 — app uses GTK4 only
    r"libgstreamer",        # GStreamer — not used
    r"libgst",              # GStreamer plugins
    r"libaom\.",            # AV1 codec
    r"libjxl\.",            # JPEG XL codec
    r"libav",               # FFmpeg libs
]))

a.datas = [d for d in a.datas if not _EXCLUDE_DATA_RE.search(d[0])]
a.binaries = [b for b in a.binaries if not _EXCLUDE_BIN_RE.search(b[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="sweep-gtk",
    debug=False,
    strip=True,
    upx=True,
    console=False,
)
