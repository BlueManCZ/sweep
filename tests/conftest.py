"""Shared test fixtures."""

from __future__ import annotations

import pytest

import sweep.storage as storage


@pytest.fixture
def isolate_storage(tmp_path, monkeypatch):
    """Redirect storage to a temp directory."""
    data_dir = tmp_path / "sweep_data"
    data_dir.mkdir()
    history_file = data_dir / "history.json"
    monkeypatch.setattr(storage, "HISTORY_FILE", history_file)
    monkeypatch.setattr(storage, "_DATA_DIR", data_dir)
    return history_file
