"""CLI interface for Sweep."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from sweep.core.engine import SweepEngine
from sweep.core.plugin_loader import load_plugins
from sweep.core.registry import PluginRegistry
from sweep.core.tracker import Tracker
from sweep.models.scan_result import FileEntry
from sweep.utils import bytes_to_human


def _setup_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _build_engine() -> SweepEngine:
    registry = PluginRegistry()
    load_plugins(registry)
    return SweepEngine(registry)


@click.group()
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v info, -vv debug)")
def main(verbose: int) -> None:
    """Sweep — a modern, modular disk cleaner for Linux."""
    _setup_logging(verbose)


# ── list ─────────────────────────────────────────────────────────────────

@main.command("list")
@click.option("--category", "-c", default=None, help="Filter by category")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def list_cmd(category: str | None, as_json: bool) -> None:
    """List available cleaning plugins."""
    engine = _build_engine()
    plugins = engine.registry.get_available()
    if category:
        plugins = [p for p in plugins if p.category == category]

    if as_json:
        data = []
        for p in plugins:
            entry = {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "requires_root": p.requires_root,
                "risk_level": p.risk_level,
            }
            if p.group:
                entry["group"] = {"id": p.group.id, "name": p.group.name}
            data.append(entry)
        click.echo(json.dumps(data, indent=2))
        return

    if not plugins:
        click.echo("No plugins available.")
        return

    # Group plugins by their group for display
    grouped: dict[str, list] = {}
    standalone: list = []
    for plugin in plugins:
        if plugin.group:
            grouped.setdefault(plugin.group.id, []).append(plugin)
        else:
            standalone.append(plugin)

    def _format_plugin(plugin, indent: str = "  ") -> None:
        root_tag = click.style(" [requires root]", fg="yellow") if plugin.requires_root else ""
        risk_tag = ""
        if plugin.risk_level == "moderate":
            risk_tag = click.style(" [moderate risk]", fg="yellow")
        elif plugin.risk_level == "aggressive":
            risk_tag = click.style(" [aggressive]", fg="red")
        click.echo(f"{indent}{click.style(plugin.id, fg='cyan', bold=True):30s}  {plugin.name}{root_tag}{risk_tag}")
        click.echo(f"{indent}  {plugin.description}")

    for group_id, members in grouped.items():
        group_name = members[0].group.name
        click.echo(f"\n  {click.style(group_name, fg='blue', bold=True)}")
        for plugin in members:
            _format_plugin(plugin, indent="    ")

    if standalone:
        if grouped:
            click.echo()
        for plugin in standalone:
            _format_plugin(plugin)


# ── scan ─────────────────────────────────────────────────────────────────

@main.command()
@click.argument("plugin_ids", nargs=-1)
@click.option("--category", "-c", default=None, help="Scan all plugins in this category")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def scan(plugin_ids: tuple[str, ...], category: str | None, as_json: bool) -> None:
    """Scan for cleanable files (preview only, never deletes)."""
    engine = _build_engine()
    ids = list(plugin_ids) if plugin_ids else None

    if not as_json:
        available = engine.registry.get_available()
        count = len(ids) if ids else len(available)
        click.echo(f"\n{click.style('🔍', bold=True)} Scanning {count} modules...\n")

    def on_progress(plugin_id: str, status: str) -> None:
        if as_json:
            return
        if status == "error":
            click.echo(f"  {click.style('✗', fg='red')} {plugin_id:35s} — error during scan")

    results = engine.scan(plugin_ids=ids, category=category, on_progress=on_progress)

    if as_json:
        data = [
            {
                "plugin_id": r.plugin_id,
                "plugin_name": r.plugin_name,
                "total_bytes": r.total_bytes,
                "file_count": len(r.entries),
                "summary": r.summary,
                "entries": [
                    {
                        "path": str(e.path),
                        "size_bytes": e.size_bytes,
                        "description": e.description,
                    }
                    for e in r.entries
                ],
            }
            for r in results
        ]
        click.echo(json.dumps(data, indent=2))
        return

    # Print results
    for result in results:
        plugin = engine.registry.get(result.plugin_id)
        root_tag = click.style(" [requires root]", fg="yellow") if (plugin and plugin.requires_root) else ""
        if result.total_bytes > 0:
            size_str = bytes_to_human(result.total_bytes)
            count = len(result.entries)
            click.echo(
                f"  {click.style('✓', fg='green')} {result.plugin_name:35s} — "
                f"{click.style(size_str, fg='green', bold=True)} ({count:,} items){root_tag}"
            )
        else:
            click.echo(f"  {click.style('·', fg='bright_black')} {result.plugin_name:35s} — nothing to clean")

    # Also show unavailable plugins
    all_plugins = list(engine.registry)
    scanned_ids = {r.plugin_id for r in results}
    for plugin in all_plugins:
        if plugin.id not in scanned_ids and not plugin.is_available():
            click.echo(
                f"  {click.style('✗', fg='bright_black')} {plugin.name:35s} — "
                f"{click.style('not available on this system', fg='bright_black')}"
            )

    total = sum(r.total_bytes for r in results)
    click.echo(f"\nTotal reclaimable: {click.style(bytes_to_human(total), fg='green', bold=True)}\n")


# ── clean ────────────────────────────────────────────────────────────────

@main.command()
@click.argument("plugin_ids", nargs=-1)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Show what would be cleaned without doing it")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def clean(plugin_ids: tuple[str, ...], yes: bool, dry_run: bool, as_json: bool) -> None:
    """Scan and clean selected plugins."""
    engine = _build_engine()
    tracker = Tracker()
    ids = list(plugin_ids) if plugin_ids else None

    # Scan first
    if not as_json:
        click.echo(f"\n{click.style('🔍', bold=True)} Scanning...\n")

    scan_results = engine.scan(plugin_ids=ids)
    actionable = [r for r in scan_results if r.total_bytes > 0]

    if not actionable:
        if as_json:
            click.echo(json.dumps({"status": "nothing_to_clean", "results": []}))
        else:
            click.echo("Nothing to clean.")
        return

    # Show preview
    if not as_json:
        for result in actionable:
            plugin = engine.registry.get(result.plugin_id)
            root_tag = click.style(" [requires root]", fg="yellow") if (plugin and plugin.requires_root) else ""
            click.echo(
                f"  {click.style('✓', fg='green')} {result.plugin_name:35s} — "
                f"{click.style(bytes_to_human(result.total_bytes), fg='green', bold=True)} "
                f"({len(result.entries):,} items){root_tag}"
            )

        total = sum(r.total_bytes for r in actionable)
        click.echo(f"\nTotal: {click.style(bytes_to_human(total), fg='green', bold=True)}\n")

    if dry_run:
        if as_json:
            data = [
                {"plugin_id": r.plugin_id, "would_free_bytes": r.total_bytes, "file_count": len(r.entries)}
                for r in actionable
            ]
            click.echo(json.dumps({"status": "dry_run", "results": data}, indent=2))
        else:
            click.echo("(dry run — no files were deleted)")
        return

    # Confirm
    if not yes and not as_json:
        choice = click.prompt("Clean all? [y/N/select]", default="n", show_default=False)
        match choice.lower():
            case "y" | "yes":
                pass
            case "select":
                ids_to_clean = _interactive_select(actionable)
                if not ids_to_clean:
                    click.echo("Nothing selected.")
                    return
                actionable = [r for r in actionable if r.plugin_id in ids_to_clean]
            case _:
                click.echo("Aborted.")
                return

    # Clean
    if not as_json:
        click.echo(f"\n{click.style('🧹', bold=True)} Cleaning...\n")

    clean_ids = [r.plugin_id for r in actionable]
    clean_results = engine.clean(plugin_ids=clean_ids)
    tracker.record(clean_results)
    tracker.save_session()

    if as_json:
        data = [
            {
                "plugin_id": r.plugin_id,
                "freed_bytes": r.freed_bytes,
                "files_removed": r.files_removed,
                "errors": r.errors,
            }
            for r in clean_results
        ]
        click.echo(json.dumps({"status": "cleaned", "results": data}, indent=2))
        return

    total_freed = 0
    for result in clean_results:
        if result.errors:
            click.echo(
                f"  {click.style('!', fg='yellow')} {result.plugin_id:35s} — "
                f"freed {bytes_to_human(result.freed_bytes)}, {len(result.errors)} error(s)"
            )
        else:
            click.echo(
                f"  {click.style('✓', fg='green')} {result.plugin_id:35s} — "
                f"freed {click.style(bytes_to_human(result.freed_bytes), fg='green', bold=True)}"
            )
        total_freed += result.freed_bytes

    click.echo(f"\nTotal freed: {click.style(bytes_to_human(total_freed), fg='green', bold=True)}\n")


def _interactive_select(results: list) -> set[str]:
    """Let the user pick which modules to clean."""
    click.echo("\nSelect modules to clean (enter numbers, comma-separated):\n")
    for i, r in enumerate(results, 1):
        click.echo(f"  [{i}] {r.plugin_name:35s} — {bytes_to_human(r.total_bytes)}")
    click.echo()
    raw = click.prompt("Selection", default="")
    if not raw.strip():
        return set()
    selected: set[str] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(results):
                selected.add(results[idx].plugin_id)
    return selected


# ── clean-as-root (internal, hidden) ──────────────────────────────────────

@main.command("clean-as-root", hidden=True)
def clean_as_root() -> None:
    """Internal command invoked via pkexec to clean as root.

    Reads a JSON payload from stdin with the shape::

        {"entries_by_plugin": {"plugin_id": [{"path": "...", "size_bytes": N}]}}

    Writes JSON results to stdout.
    """
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        click.echo(json.dumps([{"plugin_id": "unknown", "freed_bytes": 0, "files_removed": 0,
                                "errors": [f"Bad input: {exc}"]}]))
        sys.exit(1)

    raw_entries = payload.get("entries_by_plugin", {})
    engine = _build_engine()

    # Convert raw dicts to FileEntry objects
    entries_by_plugin: dict[str, list[FileEntry]] = {}
    for pid, entry_list in raw_entries.items():
        entries_by_plugin[pid] = [
            FileEntry(
                path=Path(e["path"]),
                size_bytes=e["size_bytes"],
                description="",
            )
            for e in entry_list
        ]

    results = engine.clean(
        plugin_ids=list(entries_by_plugin),
        entries_by_plugin=entries_by_plugin,
    )

    output = [
        {
            "plugin_id": r.plugin_id,
            "freed_bytes": r.freed_bytes,
            "files_removed": r.files_removed,
            "errors": r.errors,
        }
        for r in results
    ]
    click.echo(json.dumps(output))


# ── stats ────────────────────────────────────────────────────────────────

@main.command()
@click.option("--period", "-p", default="all", type=click.Choice(["today", "week", "month", "all"]))
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def stats(period: str, as_json: bool) -> None:
    """Show space freed statistics."""
    tracker = Tracker()
    data = tracker.get_stats(period)

    if as_json:
        click.echo(json.dumps(data, indent=2))
        return

    click.echo(f"\n{click.style('📊', bold=True)} Statistics ({period})\n")
    click.echo(f"  Bytes freed:    {click.style(bytes_to_human(data['bytes_freed']), fg='green', bold=True)}")
    click.echo(f"  Files removed:  {data['files_removed']:,}")
    click.echo(f"  Sessions:       {data['session_count']}")
    click.echo(f"  Lifetime total: {click.style(bytes_to_human(data['lifetime_bytes_freed']), fg='cyan', bold=True)}")

    if data["per_plugin"]:
        click.echo(f"\n  Per-plugin breakdown:")
        for pid, pstats in sorted(data["per_plugin"].items(), key=lambda x: x[1]["bytes_freed"], reverse=True):
            click.echo(f"    {pid:25s} {bytes_to_human(pstats['bytes_freed']):>10s}  ({pstats['files_removed']:,} files)")
    click.echo()


# ── plugins ──────────────────────────────────────────────────────────────

@main.group()
def plugins() -> None:
    """Plugin management commands."""


@plugins.command("list")
def plugins_list() -> None:
    """List all installed plugins with status."""
    engine = _build_engine()
    for plugin in engine.registry:
        available = plugin.is_available()
        status = click.style("available", fg="green") if available else click.style("not available", fg="bright_black")
        root_tag = click.style(" [root]", fg="yellow") if plugin.requires_root else ""
        group_tag = click.style(f" [{plugin.group.name}]", fg="blue") if plugin.group else ""
        click.echo(f"  {plugin.id:25s} {plugin.category:18s} {status}{root_tag}{group_tag}")


@plugins.command("info")
@click.argument("plugin_id")
def plugins_info(plugin_id: str) -> None:
    """Show detailed info about a plugin."""
    engine = _build_engine()
    plugin = engine.registry.get(plugin_id)
    if plugin is None:
        click.echo(f"Plugin '{plugin_id}' not found.", err=True)
        sys.exit(1)

    click.echo(f"\n  {click.style('ID:', bold=True)}          {plugin.id}")
    click.echo(f"  {click.style('Name:', bold=True)}        {plugin.name}")
    click.echo(f"  {click.style('Category:', bold=True)}    {plugin.category}")
    click.echo(f"  {click.style('Description:', bold=True)} {plugin.description}")
    click.echo(f"  {click.style('Risk Level:', bold=True)}  {plugin.risk_level}")
    click.echo(f"  {click.style('Requires Root:', bold=True)} {plugin.requires_root}")
    click.echo(f"  {click.style('Available:', bold=True)}   {plugin.is_available()}")

    if plugin.group:
        click.echo(f"  {click.style('Group:', bold=True)}       {plugin.group.name} ({plugin.group.id})")

    click.echo()


# ── service ──────────────────────────────────────────────────────────────

@main.group()
def service() -> None:
    """D-Bus service management."""


@service.command("start")
def service_start() -> None:
    """Start the D-Bus service in foreground."""
    from sweep.dbus_service import start_service

    click.echo("Starting Sweep D-Bus service...")
    start_service()
