"""Tests for the tracker module."""

from __future__ import annotations

import json

import pytest

from sweep.models.clean_result import CleanResult
from sweep.core.tracker import Tracker

pytestmark = pytest.mark.usefixtures("isolate_storage")


class TestTracker:
    def test_session_tracking(self):
        tracker = Tracker()
        results = [
            CleanResult(plugin_id="user_cache", freed_bytes=1024, files_removed=5),
            CleanResult(plugin_id="thumbnails", freed_bytes=2048, files_removed=10),
        ]
        tracker.record(results)

        assert tracker.session_bytes_freed == 1024 + 2048
        assert tracker.session_files_removed == 15

    def test_save_session(self, isolate_storage):
        tracker = Tracker()
        tracker.record([CleanResult(plugin_id="trash", freed_bytes=5000, files_removed=3)])
        tracker.save_session()

        history = json.loads(isolate_storage.read_text())
        assert "lifetime_bytes_freed" not in history
        assert len(history["sessions"]) == 1
        session = history["sessions"][0]
        assert "bytes_freed" not in session
        assert "plugins_used" not in session
        assert session["details"][0]["bytes_freed"] == 5000

    def test_multiple_sessions(self, isolate_storage):
        # Session 1
        t1 = Tracker()
        t1.record([CleanResult(plugin_id="a", freed_bytes=100, files_removed=1)])
        t1.save_session()

        # Session 2
        t2 = Tracker()
        t2.record([CleanResult(plugin_id="b", freed_bytes=200, files_removed=2)])
        t2.save_session()

        history = json.loads(isolate_storage.read_text())
        assert len(history["sessions"]) == 2

        stats = t2.get_stats("all")
        assert stats["lifetime_bytes_freed"] == 300

    def test_get_stats_all(self, isolate_storage):
        tracker = Tracker()
        tracker.record([CleanResult(plugin_id="x", freed_bytes=999, files_removed=7)])
        tracker.save_session()

        stats = tracker.get_stats("all")
        assert stats["bytes_freed"] == 999
        assert stats["files_removed"] == 7
        assert stats["session_count"] == 1
        assert stats["lifetime_bytes_freed"] == 999

    def test_session_results_cleared_after_save(self, isolate_storage):
        """Ensure results don't accumulate across multiple save_session calls."""
        tracker = Tracker()

        # First clean
        tracker.record([CleanResult(plugin_id="portage", freed_bytes=24_000, files_removed=3300)])
        tracker.save_session()

        # Second clean (same tracker instance, like SweepClient uses)
        tracker.record([CleanResult(plugin_id="browser", freed_bytes=1_000, files_removed=50)])
        tracker.save_session()

        history = json.loads(isolate_storage.read_text())
        assert len(history["sessions"]) == 2
        # Session 1: only portage
        assert history["sessions"][0]["details"][0]["bytes_freed"] == 24_000
        # Session 2: only browser, NOT portage + browser
        assert history["sessions"][1]["details"][0]["bytes_freed"] == 1_000

        stats = tracker.get_stats("all")
        assert stats["lifetime_bytes_freed"] == 25_000

    def test_empty_session_not_saved(self, isolate_storage):
        tracker = Tracker()
        tracker.save_session()
        assert not isolate_storage.exists()

class TestTrackerStats:
    def test_per_plugin_aggregation(self, isolate_storage):
        t1 = Tracker()
        t1.record([
            CleanResult(plugin_id="cache", freed_bytes=100, files_removed=5),
            CleanResult(plugin_id="trash", freed_bytes=200, files_removed=3),
        ])
        t1.save_session()

        t2 = Tracker()
        t2.record([CleanResult(plugin_id="cache", freed_bytes=150, files_removed=8)])
        t2.save_session()

        stats = t2.get_stats("all")
        assert stats["per_plugin"]["cache"]["bytes_freed"] == 250
        assert stats["per_plugin"]["cache"]["files_removed"] == 13
        assert stats["per_plugin"]["trash"]["bytes_freed"] == 200
