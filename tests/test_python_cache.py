"""Tests for Python cache plugins."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sweep.plugins.python_cache import (
    PipCachePlugin,
    PipenvCachePlugin,
    UvCachePlugin,
    VpythonCachePlugin,
    PythonStalePkgsPlugin,
)


@pytest.fixture
def fake_python_cache(tmp_path, monkeypatch):
    """Create fake cache dirs with package archives."""
    cache = tmp_path / ".cache"
    cache.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))

    # pip cache with mixed files
    pip_dir = cache / "pip"
    pip_dir.mkdir()
    (pip_dir / "requests-2.31.0.whl").write_bytes(b"w" * 500)
    (pip_dir / "flask-3.0.0.tar.gz").write_bytes(b"t" * 300)
    (pip_dir / "selfcheck.json").write_bytes(b"j" * 50)

    # uv cache
    uv_dir = cache / "uv"
    uv_dir.mkdir()
    wheels = uv_dir / "wheels"
    wheels.mkdir()
    (wheels / "numpy-1.26.0.whl").write_bytes(b"n" * 1000)
    (wheels / "pandas-2.1.0.tar.bz2").write_bytes(b"p" * 800)

    return cache


@pytest.fixture
def fake_stale_lib(tmp_path, monkeypatch):
    """Create fake pythonX.Y dirs with .dist-info packages."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

    lib_dir = home / ".local" / "lib"
    lib_dir.mkdir(parents=True)

    # Python 3.11 — will be "stale" (interpreter missing)
    py311 = lib_dir / "python3.11" / "site-packages"
    py311.mkdir(parents=True)
    (py311 / "requests-2.31.0.dist-info").mkdir()
    (py311 / "requests-2.31.0.dist-info" / "METADATA").write_bytes(b"m" * 100)
    (py311 / "urllib3-2.0.0.dist-info").mkdir()
    (py311 / "urllib3-2.0.0.dist-info" / "METADATA").write_bytes(b"m" * 80)

    # Python 3.12 — will have interpreter present
    py312 = lib_dir / "python3.12" / "site-packages"
    py312.mkdir(parents=True)
    (py312 / "flask-3.0.0.dist-info").mkdir()
    (py312 / "flask-3.0.0.dist-info" / "METADATA").write_bytes(b"m" * 90)

    # Mock shutil.which: python3.11 missing, python3.12 present
    original_which = __import__("shutil").which

    def mock_which(name):
        if name == "python3.11":
            return None
        if name == "python3.12":
            return "/usr/bin/python3.12"
        return original_which(name)

    monkeypatch.setattr("shutil.which", mock_which)

    return lib_dir


class TestPipCachePlugin:
    def test_properties(self):
        plugin = PipCachePlugin()
        assert plugin.id == "pip_cache"
        assert plugin.category == "development"
        assert plugin.group is not None
        assert plugin.group.id == "python"

    def test_scan(self, fake_python_cache):
        plugin = PipCachePlugin()
        result = plugin.scan()

        assert result.plugin_id == "pip_cache"
        assert len(result.entries) == 3
        assert result.total_bytes == 500 + 300 + 50

    def test_unavailable_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "no_cache"))
        plugin = PipCachePlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_clean_recreates_dir(self, fake_python_cache):
        plugin = PipCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)

        pip_dir = fake_python_cache / "pip"
        # Dir is recreated but empty
        assert pip_dir.is_dir()
        assert not list(pip_dir.iterdir())
        assert clean_result.freed_bytes == 500 + 300 + 50
        assert clean_result.files_removed == 3
        assert not clean_result.errors


class TestUvCachePlugin:
    def test_properties(self):
        plugin = UvCachePlugin()
        assert plugin.id == "uv_cache"
        assert plugin.category == "development"

    def test_scan(self, fake_python_cache):
        plugin = UvCachePlugin()
        result = plugin.scan()

        assert result.plugin_id == "uv_cache"
        assert len(result.entries) == 1  # wheels subdir
        assert result.total_bytes == 1000 + 800

    def test_unavailable_when_missing(self, fake_python_cache):
        plugin = PipenvCachePlugin()
        assert plugin.unavailable_reason is not None


class TestVpythonCachePlugin:
    @pytest.fixture
    def fake_vpython_cache(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))

        vpython = cache / f"vpython-root.{os.getuid()}"
        store = vpython / "store"
        store.mkdir(parents=True)
        (store / "cpython+abc123").mkdir()
        (store / "cpython+abc123" / "python3").write_bytes(b"x" * 2000)
        (store / "wheels+def456").mkdir()
        (store / "wheels+def456" / "numpy.whl").write_bytes(b"w" * 500)
        return cache

    def test_scan_suffixed(self, fake_vpython_cache):
        plugin = VpythonCachePlugin()
        result = plugin.scan()

        assert len(result.entries) == 1
        assert result.total_bytes == 2500

    def test_scan_dot_prefixed(self, tmp_path, monkeypatch):
        """Dot-prefixed .vpython-root should also be detected."""
        cache = tmp_path / ".cache"
        cache.mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))

        bare = cache / ".vpython-root"
        bare.mkdir()
        (bare / "env.tar.gz").write_bytes(b"e" * 1200)

        plugin = VpythonCachePlugin()
        result = plugin.scan()

        assert len(result.entries) == 1
        assert result.total_bytes == 1200

    def test_scan_both(self, fake_vpython_cache):
        """Both .vpython-root and vpython-root.<uid> should be scanned."""
        bare = fake_vpython_cache / ".vpython-root"
        bare.mkdir()
        (bare / "env.tar.gz").write_bytes(b"e" * 1200)

        plugin = VpythonCachePlugin()
        result = plugin.scan()

        assert len(result.entries) == 2
        assert result.total_bytes == 2500 + 1200

    def test_clean(self, fake_vpython_cache):
        plugin = VpythonCachePlugin()
        scan = plugin.scan()
        result = plugin.clean(scan.entries)

        assert result.freed_bytes == 2500
        assert result.files_removed == 2
        assert not result.errors


class TestStalePkgsPlugin:
    def test_only_reports_missing_interpreters(self, fake_stale_lib):
        plugin = PythonStalePkgsPlugin()
        result = plugin.scan()

        assert len(result.entries) == 1
        assert "python3.11" in str(result.entries[0].path)
        assert "3.12" not in str(result.entries[0].path)

    def test_entry_description(self, fake_stale_lib):
        plugin = PythonStalePkgsPlugin()
        result = plugin.scan()

        assert result.entries[0].description == "Packages for removed Python 3.11"

    def test_clean_no_recreate(self, fake_stale_lib):
        plugin = PythonStalePkgsPlugin()
        scan = plugin.scan()
        result = plugin.clean(scan.entries)

        py311_dir = fake_stale_lib / "python3.11"
        assert not py311_dir.exists()
        assert result.freed_bytes > 0
        assert not result.errors

    def test_clean_counts_files(self, fake_stale_lib):
        """files_removed counts all files in stale python directories."""
        plugin = PythonStalePkgsPlugin()
        scan = plugin.scan()
        result = plugin.clean(scan.entries)

        # python3.11 has: requests.dist-info/METADATA, urllib3.dist-info/METADATA (2 files)
        assert result.files_removed == 2

    def test_unavailable_when_no_stale(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        plugin = PythonStalePkgsPlugin()
        assert plugin.unavailable_reason is not None
