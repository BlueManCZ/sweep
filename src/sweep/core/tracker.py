"""Tracks freed space across sessions."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sweep.models.clean_result import CleanResult
from sweep.storage import load_history, save_history

log = logging.getLogger(__name__)


class Tracker:
    """Tracks and persists cleaning statistics."""

    def __init__(self) -> None:
        self._session_results: list[CleanResult] = []

    @property
    def session_bytes_freed(self) -> int:
        """Total bytes freed in the current session."""
        return sum(r.freed_bytes for r in self._session_results)

    @property
    def session_files_removed(self) -> int:
        """Total files removed in the current session."""
        return sum(r.files_removed for r in self._session_results)

    def record(self, results: list[CleanResult]) -> None:
        """Record cleaning results for the current session."""
        self._session_results.extend(results)

    def get_last_clean_time(self) -> str | None:
        """Return ISO timestamp of the most recent cleaning session, or None."""
        history = load_history()
        sessions = history.get("sessions", [])
        return sessions[-1]["timestamp"] if sessions else None

    def save_session(self) -> None:
        """Persist the current session to history."""
        if not self._session_results:
            return

        history = load_history()
        session_entry = self._build_session_entry()
        history["sessions"].append(session_entry)
        save_history(history)

        freed = _session_bytes(session_entry)
        log.info(
            "Saved session: %d bytes freed from %d plugins",
            freed,
            len({d["plugin_id"] for d in session_entry["details"]}),
        )
        self._session_results.clear()

    def get_stats(self, period: str = "all") -> dict[str, Any]:
        """Get aggregated statistics for a time period.

        Args:
            period: One of 'today', 'week', 'month', 'all'.
        """
        history = load_history()
        all_sessions = history.get("sessions", [])

        match period:
            case "today":
                cutoff = _start_of_today()
            case "week":
                cutoff = _start_of_today() - timedelta(days=7)
            case "month":
                cutoff = _start_of_today() - timedelta(days=30)
            case _:
                cutoff = None

        if cutoff is not None:
            sessions = [
                s for s in all_sessions
                if datetime.fromisoformat(s["timestamp"]) >= cutoff
            ]
        else:
            sessions = all_sessions

        total_freed = sum(_session_bytes(s) for s in sessions)
        total_files = sum(_session_files(s) for s in sessions)
        plugin_totals = self._aggregate_plugin_stats(sessions)
        lifetime = sum(_session_bytes(s) for s in all_sessions)

        return {
            "period": period,
            "bytes_freed": total_freed,
            "files_removed": total_files,
            "session_count": len(sessions),
            "lifetime_bytes_freed": lifetime,
            "per_plugin": plugin_totals,
        }

    def _build_session_entry(self) -> dict[str, Any]:
        """Build a session record from current results."""
        details = [
            {
                "plugin_id": r.plugin_id,
                "bytes_freed": r.freed_bytes,
                "files_removed": r.files_removed,
            }
            for r in self._session_results
        ]
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details,
        }

    @staticmethod
    def _aggregate_plugin_stats(sessions: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        """Aggregate per-plugin statistics across sessions."""
        totals: dict[str, dict[str, int]] = {}
        for session in sessions:
            for detail in session.get("details", []):
                pid = detail["plugin_id"]
                if pid not in totals:
                    totals[pid] = {"bytes_freed": 0, "files_removed": 0}
                totals[pid]["bytes_freed"] += detail.get("bytes_freed", 0)
                totals[pid]["files_removed"] += detail.get("files_removed", 0)
        return totals


def _session_bytes(session: dict[str, Any]) -> int:
    """Derive total bytes freed from a session's details."""
    return sum(d.get("bytes_freed", 0) for d in session.get("details", []))


def _session_files(session: dict[str, Any]) -> int:
    """Derive total files removed from a session's details."""
    return sum(d.get("files_removed", 0) for d in session.get("details", []))


def _start_of_today() -> datetime:
    """Return the start of the current UTC day."""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)
