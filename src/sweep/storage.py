"""JSON file storage for history and tracking data."""

from __future__ import annotations

import json
import logging
from typing import Any

from sweep.utils import xdg_data_home

log = logging.getLogger(__name__)

_DATA_DIR = xdg_data_home() / "sweep"

HISTORY_FILE = _DATA_DIR / "history.json"


def _ensure_data_dir() -> None:
    """Create the data directory if it doesn't exist."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_history() -> dict[str, Any]:
    """Load the history file, returning empty structure if missing."""
    if not HISTORY_FILE.exists():
        return {"sessions": []}
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        log.exception("Failed to load history file: %s", HISTORY_FILE)
        return {"sessions": []}


def save_history(data: dict[str, Any]) -> None:
    """Write the history data to disk."""
    _ensure_data_dir()
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        log.exception("Failed to save history file: %s", HISTORY_FILE)
