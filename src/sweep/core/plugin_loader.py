"""Plugin discovery and loading."""

from __future__ import annotations

import importlib
import inspect
import json
import logging
import pkgutil
from pathlib import Path
from types import ModuleType

from sweep.models.plugin import CleanPlugin, MultiDirPlugin, SimpleCacheDirPlugin
from sweep.core.registry import PluginRegistry
from sweep.utils import xdg_config_home, xdg_data_home

log = logging.getLogger(__name__)

# Abstract base classes that should not be instantiated
_ABSTRACT_BASES = {CleanPlugin, MultiDirPlugin, SimpleCacheDirPlugin}

# Standard plugin search paths
_SYSTEM_PLUGIN_DIR = Path("/usr/share/sweep/plugins")
_USER_PLUGIN_DIR = xdg_data_home() / "sweep" / "plugins"
_CONFIG_FILE = xdg_config_home() / "sweep" / "config.json"


def _find_plugins_in_module(module: ModuleType) -> list[type[CleanPlugin]]:
    """Find all CleanPlugin subclasses in a module."""
    plugins: list[type[CleanPlugin]] = []
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, CleanPlugin) and obj not in _ABSTRACT_BASES:
            plugins.append(obj)
    return plugins


def _load_builtin_plugins() -> list[type[CleanPlugin]]:
    """Load plugins from the sweep.plugins package."""
    import sweep.plugins as plugins_pkg

    found: list[type[CleanPlugin]] = []
    for importer, modname, _ispkg in pkgutil.iter_modules(plugins_pkg.__path__):
        try:
            module = importlib.import_module(f"sweep.plugins.{modname}")
            found.extend(_find_plugins_in_module(module))
        except Exception:
            log.exception("Failed to load built-in plugin module: %s", modname)
    return found


def _load_plugins_from_directory(directory: Path) -> list[type[CleanPlugin]]:
    """Load plugins from an external directory."""
    if not directory.is_dir():
        return []

    found: list[type[CleanPlugin]] = []
    for path in sorted(directory.iterdir()):
        if path.is_dir() and (path / "__init__.py").exists():
            module_file = path / "plugin.py"
            if not module_file.exists():
                module_file = path / "__init__.py"
        elif path.suffix == ".py" and path.name != "__init__.py":
            module_file = path
        else:
            continue

        try:
            spec = importlib.util.spec_from_file_location(f"sweep_ext_plugin_{path.stem}", module_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            found.extend(_find_plugins_in_module(module))
        except Exception:
            log.exception("Failed to load plugin from: %s", module_file)
    return found


def _get_config_plugin_paths() -> list[Path]:
    """Read additional plugin paths from user config."""
    if not _CONFIG_FILE.exists():
        return []
    try:
        with open(_CONFIG_FILE) as f:
            config = json.load(f)
        return [Path(p) for p in config.get("plugin_paths", [])]
    except Exception:
        log.exception("Failed to read config file: %s", _CONFIG_FILE)
        return []


def load_plugins(registry: PluginRegistry) -> None:
    """Discover and register all available plugins.

    Searches in order: built-in, system-wide, user-local, config-specified.
    """
    plugin_classes: list[type[CleanPlugin]] = []

    # 1. Built-in plugins
    plugin_classes.extend(_load_builtin_plugins())

    # 2. System-wide plugins
    plugin_classes.extend(_load_plugins_from_directory(_SYSTEM_PLUGIN_DIR))

    # 3. User-local plugins
    plugin_classes.extend(_load_plugins_from_directory(_USER_PLUGIN_DIR))

    # 4. Config-specified paths
    for path in _get_config_plugin_paths():
        plugin_classes.extend(_load_plugins_from_directory(path))

    # Instantiate and register
    for cls in plugin_classes:
        try:
            instance = cls()
            registry.register(instance)
        except Exception:
            log.exception("Failed to instantiate plugin: %s", cls.__name__)

    log.info("Loaded %d plugins", len(registry))
