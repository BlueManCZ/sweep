"""Generic JSON-backed settings store."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sweep.utils import xdg_config_home

log = logging.getLogger(__name__)

_SETTINGS_DIR = "sweep"
_SETTINGS_FILE = "settings.json"


class Settings:
    """Persistent settings backed by a JSON file.

    Uses dot-notation keys for nested access:
        settings.get("modules.selection")  # reads data["modules"]["selection"]
        settings.set("modules.selection", ["apt_cache"])  # writes + saves
    """

    _instance: Settings | None = None

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (xdg_config_home() / _SETTINGS_DIR / _SETTINGS_FILE)
        self._data: dict[str, Any] = {}
        self._load()

    @classmethod
    def instance(cls) -> Settings:
        """Return the singleton settings instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value by dot-notation key."""
        parts = key.split(".")
        node: Any = self._data
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key: str, value: Any) -> None:
        """Set a value by dot-notation key and persist to disk."""
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
        self._save()

    def _load(self) -> None:
        """Load settings from disk, gracefully handling errors."""
        if not self._path.exists():
            return
        try:
            self._data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Could not load settings from %s: %s", self._path, e)
            self._data = {}

    def _save(self) -> None:
        """Persist settings to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as e:
            log.warning("Could not save settings to %s: %s", self._path, e)
