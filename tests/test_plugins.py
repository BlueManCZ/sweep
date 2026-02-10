"""Tests for built-in plugins using mocked filesystem."""

from __future__ import annotations

import pytest
from sweep.plugins.user_cache import UserCachePlugin
from sweep.plugins.thumbnails import ThumbnailsPlugin
from sweep.plugins.trash import TrashPlugin
from sweep.plugins.tmp_files import TmpFilesPlugin
from sweep.plugins.coredumps import CoredumpsPlugin
from sweep.plugins.electron_cache import ElectronCachePlugin, ElectronBuilderCachePlugin
from sweep.plugins.darktable_cache import DarktableCachePlugin
from sweep.plugins.google_cache import GoogleXdgCachePlugin, GoogleEarthCachePlugin
from sweep.plugins.jetbrains_cache import JetBrainsCachePlugin
from sweep.plugins.e2e_testing_cache import PlaywrightCachePlugin, CypressCachePlugin
from sweep.plugins.spotify_cache import SpotifyCachePlugin
from sweep.plugins.copilot_cache import CopilotCachePlugin
from sweep.plugins.strawberry_cache import StrawberryCachePlugin
from sweep.plugins.bitwig_cache import (
    BitwigCachePlugin,
    BitwigLogsCachePlugin,
    BitwigTempProjectsCachePlugin,
)
from sweep.plugins.rotated_logs import RotatedLogsPlugin
from sweep.plugins.login_records import LoginRecordsPlugin
from sweep.plugins.old_app_logs import OldAppLogsPlugin


@pytest.fixture
def fake_cache(tmp_path, monkeypatch):
    """Create a fake ~/.cache directory."""
    cache = tmp_path / ".cache"
    cache.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))

    # Create some cache subdirs
    (cache / "some_app").mkdir()
    (cache / "some_app" / "data.bin").write_bytes(b"x" * 1024)
    (cache / "another_app").mkdir()
    (cache / "another_app" / "file.dat").write_bytes(b"y" * 2048)

    # These should be excluded
    (cache / "fontconfig").mkdir()
    (cache / "fontconfig" / "cache.dat").write_bytes(b"z" * 512)

    # These are handled by other plugins
    (cache / "thumbnails").mkdir()
    (cache / "thumbnails" / "normal").mkdir()

    return cache


@pytest.fixture
def fake_thumbs(tmp_path, monkeypatch):
    """Create a fake thumbnails directory."""
    cache = tmp_path / ".cache"
    cache.mkdir(exist_ok=True)
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))

    thumbs = cache / "thumbnails"
    thumbs.mkdir()
    normal = thumbs / "normal"
    normal.mkdir()
    (normal / "thumb1.png").write_bytes(b"p" * 500)
    (normal / "thumb2.png").write_bytes(b"p" * 300)

    large = thumbs / "large"
    large.mkdir()
    (large / "thumb3.png").write_bytes(b"p" * 800)

    return thumbs


@pytest.fixture
def fake_trash(tmp_path, monkeypatch):
    """Create a fake trash directory."""
    data_home = tmp_path / ".local" / "share"
    data_home.mkdir(parents=True)
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    trash = data_home / "Trash"
    trash.mkdir()
    files_dir = trash / "files"
    files_dir.mkdir()
    info_dir = trash / "info"
    info_dir.mkdir()

    (files_dir / "deleted_file.txt").write_bytes(b"d" * 4096)
    (info_dir / "deleted_file.txt.trashinfo").write_bytes(b"info")

    return trash


class TestUserCachePlugin:
    def test_scan_finds_cache_dirs(self, fake_cache):
        plugin = UserCachePlugin()
        result = plugin.scan()

        assert result.plugin_id == "user_cache"
        assert result.total_bytes == 1024 + 2048
        assert len(result.entries) == 2
        names = {e.path.name for e in result.entries}
        assert "some_app" in names
        assert "another_app" in names
        # Excluded dirs should not appear
        assert "fontconfig" not in names
        assert "thumbnails" not in names

    def test_clean_removes_entries(self, fake_cache):
        plugin = UserCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)

        assert clean_result.freed_bytes == 1024 + 2048
        assert clean_result.files_removed == 2
        assert not clean_result.errors
        assert not (fake_cache / "some_app").exists()
        assert not (fake_cache / "another_app").exists()
        # Excluded dirs remain
        assert (fake_cache / "fontconfig").exists()

    def test_properties(self):
        plugin = UserCachePlugin()
        assert plugin.id == "user_cache"
        assert plugin.category == "user"
        assert not plugin.requires_root
        assert plugin.risk_level == "moderate"


class TestThumbnailsPlugin:
    def test_scan(self, fake_thumbs):
        plugin = ThumbnailsPlugin()
        result = plugin.scan()

        assert result.plugin_id == "thumbnails"
        assert result.total_bytes == 500 + 300 + 800
        assert len(result.entries) == 2  # normal, large dirs

    def test_clean(self, fake_thumbs):
        plugin = ThumbnailsPlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)

        assert clean_result.freed_bytes == 500 + 300 + 800
        assert not clean_result.errors


class TestTrashPlugin:
    def test_scan(self, fake_trash):
        plugin = TrashPlugin()
        result = plugin.scan()

        assert result.plugin_id == "trash"
        assert result.total_bytes == 4096 + 4  # file + trashinfo
        assert len(result.entries) == 2

    def test_clean(self, fake_trash):
        plugin = TrashPlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)

        assert clean_result.freed_bytes == 4096 + 4
        assert not clean_result.errors
        assert not list((fake_trash / "files").iterdir())


class TestElectronCachePlugin:
    @pytest.fixture
    def fake_electron(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        electron = cache / "electron"
        electron.mkdir()
        (electron / "gpu_shader_cache").mkdir()
        (electron / "gpu_shader_cache" / "data.bin").write_bytes(b"g" * 4096)
        (electron / "code_cache").mkdir()
        (electron / "code_cache" / "wasm.bin").write_bytes(b"w" * 2048)
        eb = cache / "electron-builder"
        eb.mkdir()
        appimage = eb / "appimage"
        appimage.mkdir()
        (appimage / "appimage-12.0.1.7z").write_bytes(b"a" * 8192)
        return cache

    def test_properties(self):
        plugin = ElectronCachePlugin()
        assert plugin.id == "electron_cache"
        assert plugin.category == "application"
        assert plugin.risk_level == "safe"
        assert not plugin.requires_root

    def test_electron_builder_properties(self):
        plugin = ElectronBuilderCachePlugin()
        assert plugin.id == "electron_builder_cache"
        assert plugin.category == "application"
        assert plugin.risk_level == "safe"
        assert not plugin.requires_root

    def test_unavailable_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "no_cache"))
        plugin = ElectronCachePlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_electron_builder_unavailable_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "no_cache"))
        plugin = ElectronBuilderCachePlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_scan_electron(self, fake_electron):
        plugin = ElectronCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "electron_cache"
        assert result.total_bytes == 4096 + 2048
        assert len(result.entries) == 2
        names = {e.path.name for e in result.entries}
        assert "gpu_shader_cache" in names
        assert "code_cache" in names

    def test_scan_electron_builder(self, fake_electron):
        plugin = ElectronBuilderCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "electron_builder_cache"
        assert result.total_bytes == 8192
        assert len(result.entries) == 1
        assert result.entries[0].path.name == "appimage"

    def test_clean_electron(self, fake_electron):
        plugin = ElectronCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 4096 + 2048
        assert not clean_result.errors
        # Directory is recreated but empty
        assert (fake_electron / "electron").is_dir()
        assert not list((fake_electron / "electron").iterdir())

    def test_clean_electron_builder(self, fake_electron):
        plugin = ElectronBuilderCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 8192
        assert not clean_result.errors
        assert (fake_electron / "electron-builder").is_dir()
        assert not list((fake_electron / "electron-builder").iterdir())

    def test_has_items(self, fake_electron):
        plugin = ElectronCachePlugin()
        assert plugin.has_items() is True

    def test_has_items_empty(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        (cache / "electron").mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        plugin = ElectronCachePlugin()
        assert plugin.has_items() is False

    def test_user_cache_excludes_electron_dirs(self, fake_electron):
        """Ensure user_cache plugin skips both electron directories."""
        plugin = UserCachePlugin()
        result = plugin.scan()
        names = {e.path.name for e in result.entries}
        assert "electron" not in names
        assert "electron-builder" not in names


class TestDarktableCachePlugin:
    @pytest.fixture
    def fake_darktable(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        darktable = cache / "darktable"
        darktable.mkdir()
        mipmaps = darktable / "mipmaps-abc123.d"
        mipmaps.mkdir()
        (mipmaps / "data.bin").write_bytes(b"m" * 8192)
        (darktable / "cached_image.dat").write_bytes(b"i" * 4096)
        return darktable

    def test_properties(self):
        plugin = DarktableCachePlugin()
        assert plugin.id == "darktable_cache"
        assert plugin.category == "application"
        assert plugin.risk_level == "safe"
        assert not plugin.requires_root

    def test_unavailable_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "no_cache"))
        plugin = DarktableCachePlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_scan(self, fake_darktable):
        plugin = DarktableCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "darktable_cache"
        assert result.total_bytes == 8192 + 4096
        assert len(result.entries) == 2

    def test_clean(self, fake_darktable):
        plugin = DarktableCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 8192 + 4096
        assert clean_result.files_removed == 2
        assert not clean_result.errors
        assert not list(fake_darktable.iterdir())

    def test_has_items(self, fake_darktable):
        plugin = DarktableCachePlugin()
        assert plugin.has_items() is True

    def test_has_items_empty(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        (cache / "darktable").mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        plugin = DarktableCachePlugin()
        assert plugin.has_items() is False

    def test_user_cache_excludes_darktable(self, fake_darktable):
        """Ensure user_cache plugin skips the darktable directory."""
        plugin = UserCachePlugin()
        result = plugin.scan()
        names = {e.path.name for e in result.entries}
        assert "darktable" not in names


class TestGoogleCachePlugin:
    @pytest.fixture
    def fake_google(self, tmp_path, monkeypatch):
        """Set up both XDG cache and Google Earth home cache."""
        cache = tmp_path / ".cache"
        cache.mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        monkeypatch.setenv("HOME", str(tmp_path))
        google = cache / "Google"
        google.mkdir()
        studio = google / "AndroidStudio2024.1"
        studio.mkdir()
        (studio / "caches.bin").write_bytes(b"s" * 16384)
        earth_xdg = google / "GoogleEarth"
        earth_xdg.mkdir()
        (earth_xdg / "tiles.dat").write_bytes(b"e" * 4096)
        # Google Earth Pro home cache
        earth_home = tmp_path / ".googleearth" / "Cache"
        earth_home.mkdir(parents=True)
        (earth_home / "unified_cache").write_bytes(b"u" * 8192)
        return tmp_path

    def test_xdg_properties(self):
        plugin = GoogleXdgCachePlugin()
        assert plugin.id == "google_xdg_cache"
        assert plugin.category == "application"
        assert plugin.risk_level == "safe"
        assert not plugin.requires_root

    def test_earth_properties(self):
        plugin = GoogleEarthCachePlugin()
        assert plugin.id == "google_earth_cache"
        assert plugin.category == "application"
        assert plugin.risk_level == "safe"
        assert not plugin.requires_root

    def test_unavailable_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "no_cache"))
        monkeypatch.setenv("HOME", str(tmp_path / "no_home"))
        plugin = GoogleXdgCachePlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_earth_unavailable_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path / "no_home"))
        plugin = GoogleEarthCachePlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_scan_xdg(self, fake_google):
        plugin = GoogleXdgCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "google_xdg_cache"
        assert result.total_bytes == 16384 + 4096
        assert len(result.entries) == 2

    def test_scan_earth(self, fake_google):
        plugin = GoogleEarthCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "google_earth_cache"
        assert result.total_bytes == 8192
        assert len(result.entries) == 1

    def test_clean_xdg(self, fake_google):
        plugin = GoogleXdgCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 16384 + 4096
        assert clean_result.files_removed == 2
        assert not clean_result.errors

    def test_clean_earth(self, fake_google):
        plugin = GoogleEarthCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 8192
        assert clean_result.files_removed == 1
        assert not clean_result.errors

    def test_has_items(self, fake_google):
        plugin = GoogleXdgCachePlugin()
        assert plugin.has_items() is True

    def test_has_items_empty(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        (cache / "Google").mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        monkeypatch.setenv("HOME", str(tmp_path))
        plugin = GoogleXdgCachePlugin()
        assert plugin.has_items() is False

    def test_earth_only(self, tmp_path, monkeypatch):
        """Plugin works when only Google Earth home cache exists."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "no_cache"))
        monkeypatch.setenv("HOME", str(tmp_path))
        earth = tmp_path / ".googleearth" / "Cache"
        earth.mkdir(parents=True)
        (earth / "tiles.db").write_bytes(b"t" * 2048)
        plugin = GoogleEarthCachePlugin()
        assert plugin.is_available()
        result = plugin.scan()
        assert result.total_bytes == 2048

    def test_user_cache_excludes_google(self, fake_google):
        """Ensure user_cache plugin skips the Google directory."""
        plugin = UserCachePlugin()
        result = plugin.scan()
        names = {e.path.name for e in result.entries}
        assert "Google" not in names


class TestJetBrainsCachePlugin:
    @pytest.fixture
    def fake_jetbrains(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        jb = cache / "JetBrains"
        jb.mkdir()
        pycharm = jb / "PyCharm2024.3"
        pycharm.mkdir()
        (pycharm / "caches.bin").write_bytes(b"p" * 8192)
        idea = jb / "IntelliJIdea2024.3"
        idea.mkdir()
        (idea / "index.dat").write_bytes(b"i" * 4096)
        return jb

    def test_properties(self):
        plugin = JetBrainsCachePlugin()
        assert plugin.id == "jetbrains_cache"
        assert plugin.category == "development"
        assert plugin.risk_level == "safe"
        assert not plugin.requires_root

    def test_unavailable_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "no_cache"))
        plugin = JetBrainsCachePlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_scan(self, fake_jetbrains):
        plugin = JetBrainsCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "jetbrains_cache"
        assert result.total_bytes == 8192 + 4096
        assert len(result.entries) == 2
        names = {e.path.name for e in result.entries}
        assert "PyCharm2024.3" in names
        assert "IntelliJIdea2024.3" in names

    def test_clean(self, fake_jetbrains):
        plugin = JetBrainsCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 8192 + 4096
        assert clean_result.files_removed == 2
        assert not clean_result.errors
        assert not list(fake_jetbrains.iterdir())

    def test_has_items(self, fake_jetbrains):
        plugin = JetBrainsCachePlugin()
        assert plugin.has_items() is True

    def test_has_items_empty(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        (cache / "JetBrains").mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        plugin = JetBrainsCachePlugin()
        assert plugin.has_items() is False

    def test_user_cache_excludes_jetbrains(self, fake_jetbrains):
        """Ensure user_cache plugin skips the JetBrains directory."""
        plugin = UserCachePlugin()
        result = plugin.scan()
        names = {e.path.name for e in result.entries}
        assert "JetBrains" not in names


class TestE2eTestingCachePlugin:
    @pytest.fixture
    def fake_e2e(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        pw = cache / "ms-playwright"
        pw.mkdir()
        chromium = pw / "chromium-1208"
        chromium.mkdir()
        (chromium / "chrome-linux").mkdir()
        (chromium / "chrome-linux" / "chrome").write_bytes(b"c" * 8192)
        cy = cache / "Cypress"
        cy.mkdir()
        version = cy / "4.12.1"
        version.mkdir()
        (version / "Cypress").mkdir()
        (version / "Cypress" / "Cypress").write_bytes(b"y" * 4096)
        return cache

    def test_playwright_properties(self):
        plugin = PlaywrightCachePlugin()
        assert plugin.id == "playwright_cache"
        assert plugin.category == "development"
        assert plugin.risk_level == "safe"
        assert plugin.item_noun == "browser"
        assert not plugin.requires_root

    def test_cypress_properties(self):
        plugin = CypressCachePlugin()
        assert plugin.id == "cypress_cache"
        assert plugin.category == "development"
        assert plugin.risk_level == "safe"
        assert plugin.item_noun == "browser"
        assert not plugin.requires_root

    def test_playwright_unavailable_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "no_cache"))
        plugin = PlaywrightCachePlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_cypress_unavailable_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "no_cache"))
        plugin = CypressCachePlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_scan_playwright(self, fake_e2e):
        plugin = PlaywrightCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "playwright_cache"
        assert result.total_bytes == 8192
        assert len(result.entries) == 1
        assert result.entries[0].path.name == "chromium-1208"

    def test_scan_cypress(self, fake_e2e):
        plugin = CypressCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "cypress_cache"
        assert result.total_bytes == 4096
        assert len(result.entries) == 1
        assert result.entries[0].path.name == "4.12.1"

    def test_clean_playwright(self, fake_e2e):
        plugin = PlaywrightCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 8192
        assert not clean_result.errors
        # Directory is recreated but empty
        assert (fake_e2e / "ms-playwright").is_dir()
        assert not list((fake_e2e / "ms-playwright").iterdir())

    def test_clean_cypress(self, fake_e2e):
        plugin = CypressCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 4096
        assert not clean_result.errors
        assert (fake_e2e / "Cypress").is_dir()
        assert not list((fake_e2e / "Cypress").iterdir())

    def test_has_items(self, fake_e2e):
        plugin = PlaywrightCachePlugin()
        assert plugin.has_items() is True

    def test_has_items_empty(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        (cache / "ms-playwright").mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        plugin = PlaywrightCachePlugin()
        assert plugin.has_items() is False

    def test_user_cache_excludes_e2e_dirs(self, fake_e2e):
        """Ensure user_cache plugin skips both E2E cache directories."""
        plugin = UserCachePlugin()
        result = plugin.scan()
        names = {e.path.name for e in result.entries}
        assert "ms-playwright" not in names
        assert "Cypress" not in names


class TestSpotifyCachePlugin:
    @pytest.fixture
    def fake_spotify(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        spotify = cache / "spotify"
        spotify.mkdir()
        data = spotify / "Data"
        data.mkdir()
        (data / "audio_stream.ogg").write_bytes(b"s" * 8192)
        shader = spotify / "ShaderCache"
        shader.mkdir()
        (shader / "gpu_cache.bin").write_bytes(b"g" * 4096)
        return spotify

    def test_properties(self):
        plugin = SpotifyCachePlugin()
        assert plugin.id == "spotify_cache"
        assert plugin.category == "application"
        assert plugin.risk_level == "moderate"
        assert not plugin.requires_root

    def test_unavailable_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "no_cache"))
        plugin = SpotifyCachePlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_scan(self, fake_spotify):
        plugin = SpotifyCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "spotify_cache"
        assert result.total_bytes == 8192 + 4096
        assert len(result.entries) == 2
        names = {e.path.name for e in result.entries}
        assert "Data" in names
        assert "ShaderCache" in names

    def test_clean(self, fake_spotify):
        plugin = SpotifyCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 8192 + 4096
        assert clean_result.files_removed == 2
        assert not clean_result.errors
        assert not list(fake_spotify.iterdir())

    def test_has_items(self, fake_spotify):
        plugin = SpotifyCachePlugin()
        assert plugin.has_items() is True

    def test_has_items_empty(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        (cache / "spotify").mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        plugin = SpotifyCachePlugin()
        assert plugin.has_items() is False

    def test_user_cache_excludes_spotify(self, fake_spotify):
        """Ensure user_cache plugin skips the spotify directory."""
        plugin = UserCachePlugin()
        result = plugin.scan()
        names = {e.path.name for e in result.entries}
        assert "spotify" not in names


class TestCopilotCachePlugin:
    @pytest.fixture
    def fake_copilot(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        copilot = cache / "github-copilot"
        copilot.mkdir()
        ctx = copilot / "project-context"
        ctx.mkdir()
        (ctx / "context.db").write_bytes(b"c" * 8192)
        idx = copilot / "project-index"
        idx.mkdir()
        (idx / "index.bin").write_bytes(b"i" * 4096)
        return copilot

    def test_properties(self):
        plugin = CopilotCachePlugin()
        assert plugin.id == "copilot_cache"
        assert plugin.category == "development"
        assert plugin.risk_level == "safe"
        assert not plugin.requires_root

    def test_unavailable_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "no_cache"))
        plugin = CopilotCachePlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_scan(self, fake_copilot):
        plugin = CopilotCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "copilot_cache"
        assert result.total_bytes == 8192 + 4096
        assert len(result.entries) == 2
        names = {e.path.name for e in result.entries}
        assert "project-context" in names
        assert "project-index" in names

    def test_clean(self, fake_copilot):
        plugin = CopilotCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 8192 + 4096
        assert clean_result.files_removed == 2
        assert not clean_result.errors
        assert not list(fake_copilot.iterdir())

    def test_has_items(self, fake_copilot):
        plugin = CopilotCachePlugin()
        assert plugin.has_items() is True

    def test_has_items_empty(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        (cache / "github-copilot").mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        plugin = CopilotCachePlugin()
        assert plugin.has_items() is False

    def test_user_cache_excludes_copilot(self, fake_copilot):
        """Ensure user_cache plugin skips the github-copilot directory."""
        plugin = UserCachePlugin()
        result = plugin.scan()
        names = {e.path.name for e in result.entries}
        assert "github-copilot" not in names


class TestStrawberryCachePlugin:
    @pytest.fixture
    def fake_strawberry(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        sb = cache / "strawberry"
        sb.mkdir()
        inner = sb / "strawberry"
        inner.mkdir()
        net = inner / "networkcache"
        net.mkdir()
        (net / "response.dat").write_bytes(b"n" * 4096)
        pix = inner / "pixmapcache"
        pix.mkdir()
        (pix / "album_art.png").write_bytes(b"p" * 2048)
        return sb

    def test_properties(self):
        plugin = StrawberryCachePlugin()
        assert plugin.id == "strawberry_cache"
        assert plugin.category == "application"
        assert plugin.risk_level == "safe"
        assert not plugin.requires_root

    def test_unavailable_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "no_cache"))
        plugin = StrawberryCachePlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_scan(self, fake_strawberry):
        plugin = StrawberryCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "strawberry_cache"
        assert result.total_bytes == 4096 + 2048
        assert len(result.entries) == 1
        assert result.entries[0].path.name == "strawberry"

    def test_clean(self, fake_strawberry):
        plugin = StrawberryCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 4096 + 2048
        assert clean_result.files_removed == 2  # response.dat + album_art.png
        assert not clean_result.errors
        assert not list(fake_strawberry.iterdir())

    def test_has_items(self, fake_strawberry):
        plugin = StrawberryCachePlugin()
        assert plugin.has_items() is True

    def test_has_items_empty(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        (cache / "strawberry").mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        plugin = StrawberryCachePlugin()
        assert plugin.has_items() is False

    def test_user_cache_excludes_strawberry(self, fake_strawberry):
        """Ensure user_cache plugin skips the strawberry directory."""
        plugin = UserCachePlugin()
        result = plugin.scan()
        names = {e.path.name for e in result.entries}
        assert "strawberry" not in names


class TestBitwigCachePlugin:
    @pytest.fixture
    def fake_bitwig(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        bitwig = tmp_path / ".BitwigStudio"
        bitwig.mkdir()
        cache = bitwig / "cache"
        cache.mkdir()
        audio = cache / "audio"
        audio.mkdir()
        (audio / "preview.wav").write_bytes(b"a" * 8192)
        nitro = cache / "nitro"
        nitro.mkdir()
        (nitro / "plugin.dat").write_bytes(b"n" * 4096)
        log = bitwig / "log"
        log.mkdir()
        (log / "bitwig.log").write_bytes(b"l" * 1024)
        temp = bitwig / "temp-projects"
        temp.mkdir()
        (temp / "untitled.bwproject").write_bytes(b"t" * 2048)
        return tmp_path

    def test_properties(self):
        plugin = BitwigCachePlugin()
        assert plugin.id == "bitwig_cache"
        assert plugin.category == "application"
        assert plugin.risk_level == "safe"
        assert not plugin.requires_root

    def test_logs_properties(self):
        plugin = BitwigLogsCachePlugin()
        assert plugin.id == "bitwig_logs_cache"
        assert plugin.category == "application"

    def test_temp_projects_properties(self):
        plugin = BitwigTempProjectsCachePlugin()
        assert plugin.id == "bitwig_temp_projects_cache"
        assert plugin.category == "application"

    def test_unavailable_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path / "no_home"))
        plugin = BitwigCachePlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_scan_cache(self, fake_bitwig):
        plugin = BitwigCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "bitwig_cache"
        assert result.total_bytes == 8192 + 4096
        assert len(result.entries) == 1  # one entry for the cache dir

    def test_scan_logs(self, fake_bitwig):
        plugin = BitwigLogsCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "bitwig_logs_cache"
        assert result.total_bytes == 1024
        assert len(result.entries) == 1

    def test_scan_temp_projects(self, fake_bitwig):
        plugin = BitwigTempProjectsCachePlugin()
        result = plugin.scan()
        assert result.plugin_id == "bitwig_temp_projects_cache"
        assert result.total_bytes == 2048
        assert len(result.entries) == 1

    def test_clean_cache(self, fake_bitwig):
        plugin = BitwigCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 8192 + 4096
        assert not clean_result.errors

    def test_clean_logs(self, fake_bitwig):
        plugin = BitwigLogsCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 1024
        assert not clean_result.errors

    def test_clean_temp_projects(self, fake_bitwig):
        plugin = BitwigTempProjectsCachePlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 2048
        assert not clean_result.errors

    def test_has_items(self, fake_bitwig):
        plugin = BitwigCachePlugin()
        assert plugin.has_items() is True

    def test_has_items_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        bitwig = tmp_path / ".BitwigStudio"
        bitwig.mkdir()
        (bitwig / "cache").mkdir()
        (bitwig / "log").mkdir()
        (bitwig / "temp-projects").mkdir()
        assert BitwigCachePlugin().has_items() is False
        assert BitwigLogsCachePlugin().has_items() is False
        assert BitwigTempProjectsCachePlugin().has_items() is False


class TestPluginInterface:
    """Test that all plugins implement the CleanPlugin interface correctly."""

    PLUGINS = [
        UserCachePlugin,
        ThumbnailsPlugin,
        TrashPlugin,
        TmpFilesPlugin,
        CoredumpsPlugin,
        DarktableCachePlugin,
        JetBrainsCachePlugin,
        SpotifyCachePlugin,
        CopilotCachePlugin,
        StrawberryCachePlugin,
        ElectronCachePlugin,
        ElectronBuilderCachePlugin,
        GoogleXdgCachePlugin,
        GoogleEarthCachePlugin,
        PlaywrightCachePlugin,
        CypressCachePlugin,
        BitwigCachePlugin,
        BitwigLogsCachePlugin,
        BitwigTempProjectsCachePlugin,
        RotatedLogsPlugin,
        LoginRecordsPlugin,
        OldAppLogsPlugin,
    ]

    @pytest.mark.parametrize("plugin_cls", PLUGINS)
    def test_has_required_properties(self, plugin_cls):
        plugin = plugin_cls()
        assert isinstance(plugin.id, str) and plugin.id
        assert isinstance(plugin.name, str) and plugin.name
        assert isinstance(plugin.description, str) and plugin.description
        assert plugin.category in ("system", "user", "development", "package_manager", "browser", "mail", "application")
        assert isinstance(plugin.requires_root, bool)
        assert plugin.risk_level in ("safe", "moderate", "aggressive")

    @pytest.mark.parametrize("plugin_cls", PLUGINS)
    def test_unavailable_reason_returns_none_or_string(self, plugin_cls):
        plugin = plugin_cls()
        reason = plugin.unavailable_reason
        assert reason is None or isinstance(reason, str)

    @pytest.mark.parametrize("plugin_cls", PLUGINS)
    def test_has_items_returns_bool(self, plugin_cls):
        plugin = plugin_cls()
        result = plugin.has_items()
        assert isinstance(result, bool)

    @pytest.mark.parametrize("plugin_cls", PLUGINS)
    def test_is_available_derives_from_unavailable_reason(self, plugin_cls):
        plugin = plugin_cls()
        assert plugin.is_available() == (plugin.unavailable_reason is None)


class TestUnavailableReasonWithFixtures:
    """Test unavailable_reason returns None when the plugin's resources exist."""

    def test_trash_available(self, fake_trash):
        plugin = TrashPlugin()
        assert plugin.unavailable_reason is None
        assert plugin.is_available()

    def test_trash_has_items(self, fake_trash):
        plugin = TrashPlugin()
        assert plugin.has_items() is True

    def test_trash_empty(self, tmp_path, monkeypatch):
        data_home = tmp_path / ".local" / "share"
        data_home.mkdir(parents=True)
        monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
        trash = data_home / "Trash"
        trash.mkdir()
        (trash / "files").mkdir()
        (trash / "info").mkdir()
        plugin = TrashPlugin()
        assert plugin.unavailable_reason is None
        assert plugin.has_items() is False

    def test_thumbnails_available(self, fake_thumbs):
        plugin = ThumbnailsPlugin()
        assert plugin.unavailable_reason is None
        assert plugin.has_items() is True

    def test_user_cache_available(self, fake_cache):
        plugin = UserCachePlugin()
        assert plugin.unavailable_reason is None
        assert plugin.has_items() is True

    def test_user_cache_only_excluded(self, tmp_path, monkeypatch):
        cache = tmp_path / ".cache"
        cache.mkdir()
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
        (cache / "fontconfig").mkdir()
        (cache / "thumbnails").mkdir()
        plugin = UserCachePlugin()
        assert plugin.unavailable_reason is None
        assert plugin.has_items() is False


class TestIsAvailableDerivation:
    """Test that is_available derives from unavailable_reason on base class."""

    def test_base_plugin_defaults(self):
        from sweep.models.plugin import CleanPlugin
        from sweep.models.scan_result import ScanResult

        class MinimalPlugin(CleanPlugin):
            @property
            def id(self):
                return "minimal"

            @property
            def name(self):
                return "Minimal"

            @property
            def description(self):
                return "test"

            @property
            def category(self):
                return "user"

            def scan(self):
                return ScanResult(plugin_id="minimal", plugin_name="Minimal")

        p = MinimalPlugin()
        assert p.unavailable_reason is None
        assert p.is_available() is True
        assert p.has_items() is True

    def test_unavailable_reason_makes_unavailable(self):
        from sweep.models.plugin import CleanPlugin
        from sweep.models.scan_result import ScanResult

        class BrokenPlugin(CleanPlugin):
            @property
            def id(self):
                return "broken"

            @property
            def name(self):
                return "Broken"

            @property
            def description(self):
                return "test"

            @property
            def category(self):
                return "user"

            @property
            def unavailable_reason(self):
                return "missing dependency"

            def scan(self):
                return ScanResult(plugin_id="broken", plugin_name="Broken")

        p = BrokenPlugin()
        assert p.unavailable_reason == "missing dependency"
        assert p.is_available() is False


class TestRotatedLogsPlugin:
    @pytest.fixture
    def fake_var_log(self, tmp_path, monkeypatch):
        """Create a fake /var/log with rotated log files."""
        import sweep.plugins.rotated_logs as mod

        var_log = tmp_path / "var" / "log"
        var_log.mkdir(parents=True)
        monkeypatch.setattr(mod, "_LOG_DIR", var_log)

        # Current logs (should NOT be picked up)
        (var_log / "syslog").write_bytes(b"s" * 1024)
        (var_log / "auth.log").write_bytes(b"a" * 512)

        # Rotated logs (should be picked up)
        (var_log / "syslog.0").write_bytes(b"r" * 2048)
        (var_log / "syslog.1.gz").write_bytes(b"r" * 4096)
        (var_log / "auth.log.0").write_bytes(b"r" * 1024)
        (var_log / "messages.1.gz").write_bytes(b"r" * 8192)

        return var_log

    def test_properties(self):
        plugin = RotatedLogsPlugin()
        assert plugin.id == "rotated_logs"
        assert plugin.category == "system"
        assert plugin.requires_root is True
        assert plugin.risk_level == "safe"
        assert plugin.item_noun == "log"

    def test_unavailable_when_missing(self, tmp_path, monkeypatch):
        import sweep.plugins.rotated_logs as mod

        monkeypatch.setattr(mod, "_LOG_DIR", tmp_path / "nonexistent")
        plugin = RotatedLogsPlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_available(self, fake_var_log):
        plugin = RotatedLogsPlugin()
        assert plugin.unavailable_reason is None
        assert plugin.is_available()

    def test_has_items(self, fake_var_log):
        plugin = RotatedLogsPlugin()
        assert plugin.has_items() is True

    def test_has_items_no_rotated(self, tmp_path, monkeypatch):
        import sweep.plugins.rotated_logs as mod

        var_log = tmp_path / "var" / "log"
        var_log.mkdir(parents=True)
        monkeypatch.setattr(mod, "_LOG_DIR", var_log)
        (var_log / "syslog").write_bytes(b"s" * 1024)
        plugin = RotatedLogsPlugin()
        assert plugin.has_items() is False

    def test_scan(self, fake_var_log):
        plugin = RotatedLogsPlugin()
        result = plugin.scan()
        assert result.plugin_id == "rotated_logs"
        assert result.total_bytes == 2048 + 4096 + 1024 + 8192
        assert len(result.entries) == 4
        names = {e.path.name for e in result.entries}
        assert "syslog.0" in names
        assert "syslog.1.gz" in names
        assert "auth.log.0" in names
        assert "messages.1.gz" in names
        # Current logs should not appear
        assert "syslog" not in names
        assert "auth.log" not in names

    def test_clean(self, fake_var_log):
        plugin = RotatedLogsPlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 2048 + 4096 + 1024 + 8192
        assert clean_result.files_removed == 4
        assert not clean_result.errors
        # Rotated files removed
        assert not (fake_var_log / "syslog.0").exists()
        assert not (fake_var_log / "syslog.1.gz").exists()
        # Current logs untouched
        assert (fake_var_log / "syslog").exists()
        assert (fake_var_log / "auth.log").exists()


class TestLoginRecordsPlugin:
    @pytest.fixture
    def fake_wtmp(self, tmp_path, monkeypatch):
        """Create a fake /var/log/wtmp larger than 1 MB."""
        import sweep.plugins.login_records as mod

        wtmp = tmp_path / "wtmp"
        wtmp.write_bytes(b"w" * (2 * 1024 * 1024))  # 2 MB
        monkeypatch.setattr(mod, "_WTMP", wtmp)
        return wtmp

    def test_properties(self):
        plugin = LoginRecordsPlugin()
        assert plugin.id == "login_records"
        assert plugin.category == "system"
        assert plugin.requires_root is True
        assert plugin.risk_level == "moderate"
        assert plugin.item_noun == "record"

    def test_unavailable_when_missing(self, tmp_path, monkeypatch):
        import sweep.plugins.login_records as mod

        monkeypatch.setattr(mod, "_WTMP", tmp_path / "nonexistent")
        plugin = LoginRecordsPlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_available(self, fake_wtmp):
        plugin = LoginRecordsPlugin()
        assert plugin.unavailable_reason is None
        assert plugin.is_available()

    def test_has_items_large(self, fake_wtmp):
        plugin = LoginRecordsPlugin()
        assert plugin.has_items() is True

    def test_has_items_small(self, tmp_path, monkeypatch):
        import sweep.plugins.login_records as mod

        wtmp = tmp_path / "wtmp"
        wtmp.write_bytes(b"w" * 512)  # 512 bytes, under threshold
        monkeypatch.setattr(mod, "_WTMP", wtmp)
        plugin = LoginRecordsPlugin()
        assert plugin.has_items() is False

    def test_scan_large(self, fake_wtmp):
        plugin = LoginRecordsPlugin()
        result = plugin.scan()
        assert result.plugin_id == "login_records"
        # 2 MB - 1 MB = 1 MB reclaimable
        assert result.total_bytes == 1 * 1024 * 1024
        assert len(result.entries) == 1

    def test_scan_small(self, tmp_path, monkeypatch):
        import sweep.plugins.login_records as mod

        wtmp = tmp_path / "wtmp"
        wtmp.write_bytes(b"w" * 512)
        monkeypatch.setattr(mod, "_WTMP", wtmp)
        plugin = LoginRecordsPlugin()
        result = plugin.scan()
        assert result.total_bytes == 0
        assert len(result.entries) == 0

    def test_clean_truncates(self, fake_wtmp):
        plugin = LoginRecordsPlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 2 * 1024 * 1024
        assert clean_result.files_removed == 0  # truncated, not deleted
        assert not clean_result.errors
        # File still exists but is empty
        assert fake_wtmp.exists()
        assert fake_wtmp.stat().st_size == 0


class TestOldAppLogsPlugin:
    @pytest.fixture
    def fake_var_log(self, tmp_path, monkeypatch):
        """Create a fake /var/log with stale and fresh app logs."""
        import sweep.plugins.old_app_logs as mod

        var_log = tmp_path / "var" / "log"
        var_log.mkdir(parents=True)
        monkeypatch.setattr(mod, "_LOG_DIR", var_log)

        import time

        old_mtime = time.time() - 120 * 86400  # 120 days ago

        # Stale app logs (should be picked up)
        stale1 = var_log / "genkernel.log"
        stale1.write_bytes(b"g" * 4096)
        import os

        os.utime(stale1, (old_mtime, old_mtime))

        stale2 = var_log / "roonserver.log"
        stale2.write_bytes(b"r" * 2048)
        os.utime(stale2, (old_mtime, old_mtime))

        # Fresh app log (should NOT be picked up)
        (var_log / "fresh.log").write_bytes(b"f" * 1024)

        # Skip names (should NOT be picked up even if old)
        syslog = var_log / "syslog"
        syslog.write_bytes(b"s" * 512)
        os.utime(syslog, (old_mtime, old_mtime))

        wtmp = var_log / "wtmp"
        wtmp.write_bytes(b"w" * 256)
        os.utime(wtmp, (old_mtime, old_mtime))

        # Rotated log (should NOT be picked up — has digit parts)
        rotated = var_log / "syslog.1.gz"
        rotated.write_bytes(b"z" * 128)
        os.utime(rotated, (old_mtime, old_mtime))

        # Subdirectory (should NOT be picked up — not a regular file)
        subdir = var_log / "nginx"
        subdir.mkdir()
        (subdir / "access.log").write_bytes(b"n" * 8192)

        return var_log

    def test_properties(self):
        plugin = OldAppLogsPlugin()
        assert plugin.id == "old_app_logs"
        assert plugin.category == "system"
        assert plugin.requires_root is True
        assert plugin.risk_level == "moderate"
        assert plugin.item_noun == "log"

    def test_unavailable_when_missing(self, tmp_path, monkeypatch):
        import sweep.plugins.old_app_logs as mod

        monkeypatch.setattr(mod, "_LOG_DIR", tmp_path / "nonexistent")
        plugin = OldAppLogsPlugin()
        assert plugin.unavailable_reason is not None
        assert not plugin.is_available()

    def test_available(self, fake_var_log):
        plugin = OldAppLogsPlugin()
        assert plugin.unavailable_reason is None
        assert plugin.is_available()

    def test_has_items(self, fake_var_log):
        plugin = OldAppLogsPlugin()
        assert plugin.has_items() is True

    def test_has_items_none_stale(self, tmp_path, monkeypatch):
        import sweep.plugins.old_app_logs as mod

        var_log = tmp_path / "var" / "log"
        var_log.mkdir(parents=True)
        monkeypatch.setattr(mod, "_LOG_DIR", var_log)
        (var_log / "fresh.log").write_bytes(b"f" * 1024)
        plugin = OldAppLogsPlugin()
        assert plugin.has_items() is False

    def test_scan(self, fake_var_log):
        plugin = OldAppLogsPlugin()
        result = plugin.scan()
        assert result.plugin_id == "old_app_logs"
        assert result.total_bytes == 4096 + 2048
        assert len(result.entries) == 2
        names = {e.path.name for e in result.entries}
        assert "genkernel.log" in names
        assert "roonserver.log" in names
        # Excluded items should not appear
        assert "fresh.log" not in names
        assert "syslog" not in names
        assert "wtmp" not in names
        assert "syslog.1.gz" not in names

    def test_clean(self, fake_var_log):
        plugin = OldAppLogsPlugin()
        result = plugin.scan()
        clean_result = plugin.clean(result.entries)
        assert clean_result.freed_bytes == 4096 + 2048
        assert clean_result.files_removed == 2
        assert not clean_result.errors
        assert not (fake_var_log / "genkernel.log").exists()
        assert not (fake_var_log / "roonserver.log").exists()
        # Fresh log and skip names untouched
        assert (fake_var_log / "fresh.log").exists()
        assert (fake_var_log / "syslog").exists()
