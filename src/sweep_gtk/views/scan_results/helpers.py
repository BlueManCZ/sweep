"""Helper functions for scan results formatting."""

from __future__ import annotations

from pathlib import Path

from sweep.utils import bytes_to_human


def _format_subtitle(total_bytes: int, total_items: int, noun: str, entry_count: int) -> str:
    """Build the standard 'size · N items · M entries' subtitle."""
    return (
        f"{bytes_to_human(total_bytes)}  \u00b7  "
        f"{total_items:,} {noun}{'s' if total_items != 1 else ''}  \u00b7  "
        f"{entry_count} entr{'ies' if entry_count != 1 else 'y'}"
    )


def _common_parent(paths: list[Path]) -> Path:
    """Find the deepest common parent directory for a list of paths."""
    if not paths:
        return Path("/")
    if len(paths) == 1:
        return paths[0].parent

    common = paths[0].parent
    for p in paths[1:]:
        parent = p.parent
        while common != parent and common != Path("/"):
            if str(parent).startswith(str(common)):
                break
            common = common.parent
    return common
