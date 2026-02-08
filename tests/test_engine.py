"""Tests for the scan/clean engine."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from sweep.models.plugin import CleanPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult
from sweep.core.registry import PluginRegistry
from sweep.core.engine import SweepEngine


class FakePlugin(CleanPlugin):
    """Test plugin that doesn't touch the filesystem."""

    def __init__(
        self,
        plugin_id: str = "fake",
        available: bool = True,
        fail: bool = False,
        root: bool = False,
        scan_delay: float = 0,
    ):
        self._id = plugin_id
        self._available = available
        self._fail = fail
        self._root = root
        self._scan_delay = scan_delay

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return f"Fake Plugin ({self._id})"

    @property
    def description(self) -> str:
        return "A fake plugin for testing"

    @property
    def category(self) -> str:
        return "user"

    @property
    def requires_root(self) -> bool:
        return self._root

    def is_available(self) -> bool:
        return self._available

    def scan(self) -> ScanResult:
        if self._scan_delay:
            time.sleep(self._scan_delay)
        if self._fail:
            raise RuntimeError("scan failed")
        return ScanResult(
            plugin_id=self._id,
            plugin_name=self.name,
            entries=[FileEntry(path=Path("/tmp/fake"), size_bytes=1024, description="fake file")],
            total_bytes=1024,
            summary="Found 1 fake file",
        )

    def clean(self, entries: list[FileEntry] | None = None) -> CleanResult:
        if self._fail:
            raise RuntimeError("clean failed")
        return CleanResult(plugin_id=self._id, freed_bytes=1024, files_removed=1)


@pytest.fixture
def engine():
    registry = PluginRegistry()
    registry.register(FakePlugin("alpha"))
    registry.register(FakePlugin("beta"))
    registry.register(FakePlugin("unavailable", available=False))
    return SweepEngine(registry)


class TestSweepEngine:
    def test_scan_all_available(self, engine):
        results = engine.scan()
        assert len(results) == 2  # alpha, beta (not unavailable)
        ids = {r.plugin_id for r in results}
        assert ids == {"alpha", "beta"}

    def test_scan_specific_plugins(self, engine):
        results = engine.scan(plugin_ids=["alpha"])
        assert len(results) == 1
        assert results[0].plugin_id == "alpha"

    def test_scan_caches_results(self, engine):
        engine.scan(plugin_ids=["alpha"])
        cached = engine.get_last_scan("alpha")
        assert cached is not None
        assert cached.plugin_id == "alpha"

    def test_clean_uses_last_scan(self, engine):
        engine.scan()
        results = engine.clean()
        assert len(results) == 2

    def test_clean_specific_plugins(self, engine):
        engine.scan()
        results = engine.clean(plugin_ids=["beta"])
        assert len(results) == 1
        assert results[0].plugin_id == "beta"

    def test_scan_handles_plugin_errors(self):
        registry = PluginRegistry()
        registry.register(FakePlugin("good"))
        registry.register(FakePlugin("bad", fail=True))
        engine = SweepEngine(registry)

        results = engine.scan()
        assert len(results) == 1
        assert results[0].plugin_id == "good"

    def test_clean_handles_plugin_errors(self):
        registry = PluginRegistry()
        registry.register(FakePlugin("bad", fail=True))
        engine = SweepEngine(registry)

        results = engine.clean(plugin_ids=["bad"])
        assert len(results) == 1
        assert results[0].plugin_id == "bad"
        assert results[0].errors

    def test_progress_callback(self, engine):
        events: list[tuple[str, str]] = []
        engine.scan(on_progress=lambda pid, status: events.append((pid, status)))
        assert ("alpha", "scanning") in events
        assert ("alpha", "done") in events

    def test_clean_clears_scan_cache(self, engine):
        engine.scan(plugin_ids=["alpha"])
        assert engine.get_last_scan("alpha") is not None
        engine.clean(plugin_ids=["alpha"])
        assert engine.get_last_scan("alpha") is None

    def test_clean_escalates_root_plugin_via_pkexec(self, monkeypatch):
        monkeypatch.setattr("sweep.core.engine.is_root", lambda: False)
        monkeypatch.setattr("sweep.core.engine.pkexec_available", lambda: True)
        monkeypatch.setattr(
            "sweep.core.engine.run_privileged_clean",
            lambda entries: [
                {"plugin_id": "needs_root", "freed_bytes": 2048, "files_removed": 2, "errors": []},
            ],
        )

        registry = PluginRegistry()
        registry.register(FakePlugin("needs_root", root=True))
        engine = SweepEngine(registry)
        engine.scan(plugin_ids=["needs_root"])

        results = engine.clean(plugin_ids=["needs_root"])
        assert len(results) == 1
        assert results[0].freed_bytes == 2048
        assert results[0].files_removed == 2
        assert not results[0].errors

    def test_clean_falls_back_when_pkexec_unavailable(self, monkeypatch):
        monkeypatch.setattr("sweep.core.engine.is_root", lambda: False)
        monkeypatch.setattr("sweep.core.engine.pkexec_available", lambda: False)

        registry = PluginRegistry()
        registry.register(FakePlugin("needs_root", root=True))
        engine = SweepEngine(registry)

        results = engine.clean(plugin_ids=["needs_root"])
        assert len(results) == 1
        assert results[0].freed_bytes == 0
        assert any("pkexec not available" in e for e in results[0].errors)

    def test_clean_partitions_root_and_nonroot(self, monkeypatch):
        monkeypatch.setattr("sweep.core.engine.is_root", lambda: False)
        monkeypatch.setattr("sweep.core.engine.pkexec_available", lambda: True)
        monkeypatch.setattr(
            "sweep.core.engine.run_privileged_clean",
            lambda entries: [
                {"plugin_id": "root_plugin", "freed_bytes": 5000, "files_removed": 3, "errors": []},
            ],
        )

        registry = PluginRegistry()
        registry.register(FakePlugin("normal"))
        registry.register(FakePlugin("root_plugin", root=True))
        engine = SweepEngine(registry)
        engine.scan()

        results = engine.clean()
        assert len(results) == 2
        ids = {r.plugin_id for r in results}
        assert ids == {"normal", "root_plugin"}

        normal = next(r for r in results if r.plugin_id == "normal")
        assert normal.freed_bytes == 1024

        root = next(r for r in results if r.plugin_id == "root_plugin")
        assert root.freed_bytes == 5000

    def test_clean_handles_user_cancel(self, monkeypatch):
        from sweep.core.privileges import PrivilegeError

        monkeypatch.setattr("sweep.core.engine.is_root", lambda: False)
        monkeypatch.setattr("sweep.core.engine.pkexec_available", lambda: True)
        monkeypatch.setattr(
            "sweep.core.engine.run_privileged_clean",
            lambda entries: (_ for _ in ()).throw(PrivilegeError("Authentication dismissed by user")),
        )

        registry = PluginRegistry()
        registry.register(FakePlugin("normal"))
        registry.register(FakePlugin("needs_root", root=True))
        engine = SweepEngine(registry)
        engine.scan()

        results = engine.clean()
        assert len(results) == 2

        # Non-root plugin should succeed
        normal = next(r for r in results if r.plugin_id == "normal")
        assert normal.freed_bytes == 1024
        assert not normal.errors

        # Root plugin should have an error
        root = next(r for r in results if r.plugin_id == "needs_root")
        assert root.freed_bytes == 0
        assert any("dismissed" in e.lower() for e in root.errors)

    def test_clean_allows_root_plugin_when_running_as_root(self, monkeypatch):
        monkeypatch.setattr("sweep.core.engine.is_root", lambda: True)

        registry = PluginRegistry()
        registry.register(FakePlugin("needs_root", root=True))
        engine = SweepEngine(registry)

        results = engine.clean(plugin_ids=["needs_root"])
        assert len(results) == 1
        assert results[0].freed_bytes == 1024
        assert not results[0].errors

    def test_clean_normal_plugin_still_works(self, monkeypatch):
        monkeypatch.setattr("sweep.core.engine.is_root", lambda: False)

        registry = PluginRegistry()
        registry.register(FakePlugin("normal"))
        engine = SweepEngine(registry)

        results = engine.clean(plugin_ids=["normal"])
        assert len(results) == 1
        assert results[0].freed_bytes == 1024

    def test_scan_on_result_callback(self, engine):
        """on_result fires once per successful plugin scan."""
        received: list[ScanResult] = []
        engine.scan(on_result=lambda r: received.append(r))
        assert len(received) == 2
        assert {r.plugin_id for r in received} == {"alpha", "beta"}

    def test_scan_on_result_not_called_for_errors(self):
        """on_result is NOT called when a plugin raises during scan."""
        registry = PluginRegistry()
        registry.register(FakePlugin("good"))
        registry.register(FakePlugin("bad", fail=True))
        engine = SweepEngine(registry)

        received: list[ScanResult] = []
        engine.scan(on_result=lambda r: received.append(r))
        assert len(received) == 1
        assert received[0].plugin_id == "good"

    def test_clean_on_result_callback(self, engine):
        """on_result fires for each cleaned plugin."""
        engine.scan()
        received: list[CleanResult] = []
        engine.clean(on_result=lambda r: received.append(r))
        assert len(received) == 2
        assert {r.plugin_id for r in received} == {"alpha", "beta"}

    def test_clean_on_result_called_for_errors(self):
        """on_result fires even when a plugin crashes during clean."""
        registry = PluginRegistry()
        registry.register(FakePlugin("bad", fail=True))
        engine = SweepEngine(registry)

        received: list[CleanResult] = []
        engine.clean(plugin_ids=["bad"], on_result=lambda r: received.append(r))
        assert len(received) == 1
        assert received[0].plugin_id == "bad"
        assert received[0].errors

    def test_fake_plugin_is_available_override(self):
        """FakePlugin overrides is_available() directly and still works."""
        available = FakePlugin("a", available=True)
        assert available.is_available() is True
        # unavailable_reason is None (base default), but is_available is overridden
        assert available.unavailable_reason is None

        unavailable = FakePlugin("b", available=False)
        assert unavailable.is_available() is False
        # has_items defaults to True from base
        assert unavailable.has_items() is True

    def test_scan_runs_plugins_concurrently(self):
        """Plugins scan in parallel via thread pool (4 workers)."""
        delay = 0.1
        count = 4
        registry = PluginRegistry()
        for i in range(count):
            registry.register(FakePlugin(f"slow_{i}", scan_delay=delay))
        engine = SweepEngine(registry)

        start = time.monotonic()
        results = engine.scan()
        elapsed = time.monotonic() - start

        assert len(results) == count
        # Sequential would take count * delay = 0.4s; parallel should be ~0.1s
        assert elapsed < delay * count * 0.75

    def test_scan_single_plugin_no_overhead(self):
        """A single plugin skips the thread pool (len < 2)."""
        registry = PluginRegistry()
        registry.register(FakePlugin("only", scan_delay=0.05))
        engine = SweepEngine(registry)

        start = time.monotonic()
        results = engine.scan()
        elapsed = time.monotonic() - start

        assert len(results) == 1
        assert elapsed < 0.15  # no thread pool overhead
