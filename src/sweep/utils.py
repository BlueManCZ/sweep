"""Shared utility functions."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from sweep.models.scan_result import FileEntry

log = logging.getLogger(__name__)


def has_command(name: str) -> bool:
    """Check if a command exists on the system."""
    try:
        subprocess.run(["which", name], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def xdg_cache_home() -> Path:
    """Return XDG_CACHE_HOME, defaulting to ~/.cache."""
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))


def xdg_config_home() -> Path:
    """Return XDG_CONFIG_HOME, defaulting to ~/.config."""
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def xdg_data_home() -> Path:
    """Return XDG_DATA_HOME, defaulting to ~/.local/share."""
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def remove_entries(
    entries: list[FileEntry],
    *,
    count_files: bool = False,
    recreate_dirs: bool = False,
) -> tuple[int, int, list[str]]:
    """Remove file entries and return (freed_bytes, files_removed, errors).

    Args:
        entries: FileEntry items to remove.
        count_files: If True, count individual files in directories.
                     If False, count each entry as 1 removal.
        recreate_dirs: If True, recreate directories after removal.
    """
    freed = 0
    removed = 0
    errors: list[str] = []

    for entry in entries:
        try:
            if entry.path.is_dir():
                if count_files:
                    removed += sum(1 for f in entry.path.rglob("*") if f.is_file())
                else:
                    removed += 1
                shutil.rmtree(entry.path)
                if recreate_dirs:
                    entry.path.mkdir(parents=True, exist_ok=True)
            elif entry.path.exists():
                entry.path.unlink()
                removed += 1
            freed += entry.size_bytes
        except OSError as e:
            errors.append(f"{entry.path}: {e}")

    return freed, removed, errors


def dir_info(path: Path | str) -> tuple[int, int]:
    """Calculate total size and file count of a directory tree.

    Uses GNU ``find`` (C-speed walk) when available, falling back to
    ``os.scandir`` on systems without it.

    Returns:
        (total_bytes, file_count) tuple.
    """
    try:
        return _dir_info_find(str(path))
    except Exception:
        return _dir_info_scandir(path)


def _dir_info_find(path_str: str) -> tuple[int, int]:
    """Walk a directory tree using GNU find (pure C, no Python per-file overhead)."""
    proc = subprocess.run(
        ["find", path_str, "-type", "f", "-printf", "%s\n"],
        capture_output=True, timeout=60,
    )
    total = count = 0
    for line in proc.stdout.split(b"\n"):
        if line:
            total += int(line)
            count += 1
    return total, count


def _dir_info_scandir(path: Path | str) -> tuple[int, int]:
    """Walk a directory tree using os.scandir (pure Python fallback)."""
    total = 0
    count = 0
    stack: list[Path | str] = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                            count += 1
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except OSError:
                        pass
        except OSError:
            pass
    return total, count


def dir_size(path: Path) -> int:
    """Calculate total size of a directory tree."""
    return dir_info(path)[0]


def bytes_to_human(size_bytes: int) -> str:
    """Convert byte count to a human-readable string."""
    if size_bytes < 0:
        return f"-{bytes_to_human(-size_bytes)}"
    if size_bytes == 0:
        return "0 B"

    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size_bytes)
    for unit in units[:-1]:
        if abs(value) < 1024:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} {units[-1]}"


def format_relative_time(iso_timestamp: str) -> str:
    """Format an ISO timestamp as relative time ('2 hours ago')."""
    from datetime import datetime, timezone

    dt = datetime.fromisoformat(iso_timestamp)
    seconds = int((datetime.now(timezone.utc) - dt).total_seconds())

    if seconds < 60:
        return "just now"
    if seconds < 3600:
        m = seconds // 60
        return f"{m} minute{'s' if m != 1 else ''} ago"
    if seconds < 86400:
        h = seconds // 3600
        return f"{h} hour{'s' if h != 1 else ''} ago"
    d = seconds // 86400
    if d < 30:
        return f"{d} day{'s' if d != 1 else ''} ago"
    mo = d // 30
    if mo < 12:
        return f"{mo} month{'s' if mo != 1 else ''} ago"
    y = d // 365
    return f"{y} year{'s' if y != 1 else ''} ago"


def format_elapsed(seconds: float) -> str:
    """Format an elapsed time as a human-readable string."""
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds) // 60
    secs = seconds - minutes * 60
    return f"{minutes}m {secs:.0f}s"
