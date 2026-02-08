"""Tests for the Portage plugins."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from sweep.models.scan_result import FileEntry
from sweep.plugins.portage_cache import (
    PortageDepcleanPlugin,
    PortageDistfilesPlugin,
    PortagePackagesPlugin,
    _get_installed_size,
)


class TestGetInstalledSize:
    def test_reads_size_file(self, tmp_path):
        vdb = tmp_path / "var" / "db" / "pkg"
        pkg_dir = vdb / "dev-libs" / "libfoo-1.0"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "SIZE").write_text("12345\n")

        with patch("sweep.plugins.portage_cache._VDB_PATH", vdb):
            assert _get_installed_size("dev-libs/libfoo-1.0") == 12345

    def test_missing_size_file(self, tmp_path):
        vdb = tmp_path / "var" / "db" / "pkg"
        vdb.mkdir(parents=True)

        with patch("sweep.plugins.portage_cache._VDB_PATH", vdb):
            assert _get_installed_size("dev-libs/nonexistent-1.0") == 0

    def test_invalid_size_content(self, tmp_path):
        vdb = tmp_path / "var" / "db" / "pkg"
        pkg_dir = vdb / "dev-libs" / "libfoo-1.0"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "SIZE").write_text("not a number\n")

        with patch("sweep.plugins.portage_cache._VDB_PATH", vdb):
            assert _get_installed_size("dev-libs/libfoo-1.0") == 0


class TestDepcleanPlugin:
    @pytest.fixture
    def plugin(self):
        with patch("sweep.plugins.portage_cache._portage_available", return_value=True):
            return PortageDepcleanPlugin()

    def test_properties(self, plugin):
        assert plugin.id == "portage_depclean"
        assert plugin.name == "Orphaned Packages"
        assert plugin.requires_root is True
        assert plugin.item_noun == "package"

    def test_unavailable_without_portage(self):
        with patch("sweep.plugins.portage_cache._portage_available", return_value=False):
            plugin = PortageDepcleanPlugin()
            assert plugin.unavailable_reason is not None
            assert not plugin.is_available()

    def test_available_without_gentoolkit(self):
        """Depclean does not need gentoolkit."""
        with (
            patch("sweep.plugins.portage_cache._portage_available", return_value=True),
            patch("sweep.plugins.portage_cache._gentoolkit_available", return_value=False),
        ):
            plugin = PortageDepcleanPlugin()
            assert plugin.unavailable_reason is None

    def test_scan(self, plugin, tmp_path):
        vdb = tmp_path / "var" / "db" / "pkg"
        pkg_a = vdb / "dev-libs" / "libfoo-1.0"
        pkg_a.mkdir(parents=True)
        (pkg_a / "SIZE").write_text("50000\n")

        pkg_b = vdb / "app-misc" / "bar-2.3"
        pkg_b.mkdir(parents=True)
        (pkg_b / "SIZE").write_text("30000\n")

        with (
            patch("sweep.plugins.portage_cache._VDB_PATH", vdb),
            patch(
                "sweep.plugins.portage_cache._calc_depclean_candidates",
                return_value=["dev-libs/libfoo-1.0", "app-misc/bar-2.3"],
            ),
        ):
            result = plugin.scan()

        assert len(result.entries) == 2
        assert result.total_bytes == 80000
        assert result.entries[0].description == "dev-libs/libfoo-1.0"
        assert result.entries[1].description == "app-misc/bar-2.3"
        assert result.entries[0].path == vdb / "dev-libs" / "libfoo-1.0"

    def test_scan_empty(self, plugin):
        with patch(
            "sweep.plugins.portage_cache._calc_depclean_candidates",
            return_value=[],
        ):
            result = plugin.scan()

        assert len(result.entries) == 0
        assert result.total_bytes == 0

    def test_scan_resolver_failure(self, plugin):
        with patch(
            "sweep.plugins.portage_cache._calc_depclean_candidates",
            side_effect=RuntimeError("calc_depclean returned exit code 1"),
        ):
            with pytest.raises(RuntimeError, match="calc_depclean"):
                plugin.scan()

    def test_clean(self, plugin, tmp_path):
        vdb = tmp_path / "var" / "db" / "pkg"
        vdb.mkdir(parents=True)

        entries = [
            FileEntry(
                path=vdb / "dev-libs" / "libfoo-1.0",
                size_bytes=50000,
                description="dev-libs/libfoo-1.0",
            ),
            FileEntry(
                path=vdb / "app-misc" / "bar-2.3",
                size_bytes=30000,
                description="app-misc/bar-2.3",
            ),
        ]

        with (
            patch("sweep.plugins.portage_cache._VDB_PATH", vdb),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""

            result = plugin.clean(entries=entries)

        assert result.freed_bytes == 80000
        assert result.files_removed == 2
        assert not result.errors

        # Verify emerge was called with correct atoms
        call_args = mock_run.call_args[0][0]
        assert "emerge" in call_args[0]
        assert "--depclean" in call_args
        assert "=dev-libs/libfoo-1.0" in call_args
        assert "=app-misc/bar-2.3" in call_args

    def test_clean_failure(self, plugin, tmp_path):
        vdb = tmp_path / "var" / "db" / "pkg"
        vdb.mkdir(parents=True)

        entries = [
            FileEntry(
                path=vdb / "dev-libs" / "libfoo-1.0",
                size_bytes=50000,
                description="dev-libs/libfoo-1.0",
            ),
        ]

        with (
            patch("sweep.plugins.portage_cache._VDB_PATH", vdb),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "Permission denied"

            result = plugin.clean(entries=entries)

        assert result.freed_bytes == 0
        assert len(result.errors) == 1
        assert "Permission denied" in result.errors[0]

    def test_clean_no_entries(self, plugin):
        result = plugin.clean(entries=[])
        assert result.freed_bytes == 0
        assert not result.errors


class TestDistfilesPlugin:
    def test_unavailable_without_gentoolkit(self):
        with (
            patch("sweep.plugins.portage_cache._portage_available", return_value=True),
            patch("sweep.plugins.portage_cache._gentoolkit_available", return_value=False),
        ):
            plugin = PortageDistfilesPlugin()
            assert plugin.unavailable_reason is not None

    def test_unavailable_without_portage(self):
        with patch("sweep.plugins.portage_cache._portage_available", return_value=False):
            plugin = PortageDistfilesPlugin()
            assert plugin.unavailable_reason is not None


class TestPackagesPlugin:
    def test_unavailable_without_gentoolkit(self):
        with (
            patch("sweep.plugins.portage_cache._portage_available", return_value=True),
            patch("sweep.plugins.portage_cache._gentoolkit_available", return_value=False),
        ):
            plugin = PortagePackagesPlugin()
            assert plugin.unavailable_reason is not None

    def test_unavailable_without_portage(self):
        with patch("sweep.plugins.portage_cache._portage_available", return_value=False):
            plugin = PortagePackagesPlugin()
            assert plugin.unavailable_reason is not None


class TestPluginAvailability:
    def test_depclean_available_with_portage_only(self):
        with (
            patch("sweep.plugins.portage_cache._portage_available", return_value=True),
            patch("sweep.plugins.portage_cache._gentoolkit_available", return_value=False),
        ):
            plugin = PortageDepcleanPlugin()
            assert plugin.unavailable_reason is None
            assert plugin.is_available()

    def test_depclean_unavailable_without_portage(self):
        with patch("sweep.plugins.portage_cache._portage_available", return_value=False):
            plugin = PortageDepcleanPlugin()
            assert plugin.unavailable_reason is not None
            assert not plugin.is_available()
