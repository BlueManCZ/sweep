"""Dashboard view — quick scan summary, cleaning history, reclaimable breakdown."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, GLib

from sweep.utils import bytes_to_human, format_relative_time
from sweep_gtk.constants import CATEGORY_LABELS
from sweep_gtk.widgets import icon_label as _icon_label

if TYPE_CHECKING:
    from sweep_gtk.window import SweepWindow

# Categories excluded from the dashboard quick scan (too slow for background use)
_SLOW_CATEGORIES = {"package_manager"}


class DashboardView(Gtk.Box):
    """Dashboard with quick-scan results, stats cards, and cleaning history."""

    def __init__(self, window: SweepWindow) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self._scan_generation: int = 0
        self._scan_results: list[dict] = []

        # Plugin metadata for display names, categories, and group info
        self._plugin_info: dict[str, dict] = {
            p["id"]: p for p in self.window.client.list_plugins()
        }

        # ── Scrolled container ────────────────────────────────
        scrolled = Gtk.ScrolledWindow(
            vexpand=True,
            hexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        self.append(scrolled)

        self.content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )
        scrolled.set_child(self.content_box)

        # ── Hero section (icon + title + description) ─────────
        self._hero_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
            margin_top=24,
            margin_bottom=8,
        )
        self.content_box.append(self._hero_box)

        self._hero_icon = Gtk.Image.new_from_icon_name("edit-clear-all-symbolic")
        self._hero_icon.set_pixel_size(96)
        self._hero_icon.set_margin_bottom(8)
        self._hero_box.append(self._hero_icon)

        self._hero_title = Gtk.Label(label="Quick Scanning\u2026")
        self._hero_title.add_css_class("title-1")
        self._hero_box.append(self._hero_title)

        self._hero_description = Gtk.Label()
        self._hero_description.add_css_class("dim-label")
        self._hero_description.set_wrap(True)
        self._hero_description.set_justify(Gtk.Justification.CENTER)
        self._hero_box.append(self._hero_description)

        # Scan progress indicator (visible during quick scan)
        self._scan_progress = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        self._scan_spinner = Gtk.Spinner(spinning=True)
        self._scan_progress.append(self._scan_spinner)
        scan_label = Gtk.Label(label="Checking for reclaimable space\u2026")
        scan_label.add_css_class("dim-label")
        self._scan_progress.append(scan_label)
        self._hero_box.append(self._scan_progress)

        # ── Action buttons ─────────────────────────────────────
        self._button_box = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        self._button_box.set_visible(False)
        self.content_box.append(self._button_box)

        self._review_btn = Gtk.Button(
            child=_icon_label("edit-clear-all-symbolic", "Review & Clean"),
        )
        self._review_btn.add_css_class("suggested-action")
        self._review_btn.add_css_class("pill")
        self._review_btn.connect("clicked", self._on_review_clean)
        self._review_btn.set_visible(False)
        self._button_box.append(self._review_btn)

        self._secondary_btns = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        self._button_box.append(self._secondary_btns)

        self._safe_scan_btn = Gtk.Button(
            child=_icon_label("security-high-symbolic", "Safe Scan"),
        )
        self._safe_scan_btn.add_css_class("pill")
        self._safe_scan_btn.connect("clicked", self._on_safe_scan)
        self._secondary_btns.append(self._safe_scan_btn)

        self._full_scan_btn = Gtk.Button(
            child=_icon_label("edit-select-all-symbolic", "Full Scan"),
        )
        self._full_scan_btn.add_css_class("pill")
        self._full_scan_btn.connect("clicked", self._on_full_scan)
        self._secondary_btns.append(self._full_scan_btn)

        # ── Reclaimable breakdown ──────────────────────────────
        self._breakdown_group = Adw.PreferencesGroup(title="Reclaimable Space")
        self._breakdown_group.set_visible(False)
        self._breakdown_rows: list[Adw.ExpanderRow] = []
        self._level_bars: list[Gtk.LevelBar] = []
        self._size_labels: list[Gtk.Label] = []
        breakdown_clamp = Adw.Clamp(maximum_size=600, child=self._breakdown_group)
        self.content_box.append(breakdown_clamp)

        # ── Stats cards (historical, hidden until first clean) ─
        self.stats_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            homogeneous=True,
        )
        self.stats_box.set_visible(False)
        stats_clamp = Adw.Clamp(maximum_size=500, child=self.stats_box)
        self.content_box.append(stats_clamp)

        self.card_today = self._create_stat_card("Today", "0 B")
        self.card_week = self._create_stat_card("This Week", "0 B")
        self.card_lifetime = self._create_stat_card("All Time", "0 B")
        self.stats_box.append(self.card_today)
        self.stats_box.append(self.card_week)
        self.stats_box.append(self.card_lifetime)

        # ── Historical per-module breakdown ────────────────────
        self._history_group = Adw.PreferencesGroup(title="Cleaning History")
        self._history_group.set_visible(False)
        self._history_rows: list[Adw.ExpanderRow] = []

        history_clamp = Adw.Clamp(maximum_size=600, child=self._history_group)
        self.content_box.append(history_clamp)

        # ── Responsive layout ─────────────────────────────────
        self._layout_mode = "wide"
        scrolled.get_hadjustment().connect(
            "notify::page-size", self._on_viewport_resize
        )

        # Load historical stats and kick off the quick scan
        self._refresh_stats()
        self._start_quick_scan()

    def _create_stat_card(self, title: str, value: str) -> Gtk.Frame:
        """Create a styled statistics card."""
        frame = Gtk.Frame()
        frame.add_css_class("card")

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=16,
            margin_bottom=16,
            margin_start=12,
            margin_end=12,
        )
        frame.set_child(box)

        value_label = Gtk.Label(label=value)
        value_label.add_css_class("title-1")
        box.append(value_label)

        title_label = Gtk.Label(label=title)
        title_label.add_css_class("dim-label")
        box.append(title_label)

        frame._value_label = value_label
        return frame

    # ── Quick scan ────────────────────────────────────────────

    def _start_quick_scan(self) -> None:
        """Launch a background quick scan (excludes slow categories)."""
        self._scan_generation += 1
        gen = self._scan_generation

        quick_ids = [
            pid for pid, info in self._plugin_info.items()
            if info["available"] and info["category"] not in _SLOW_CATEGORIES
        ]

        if not quick_ids:
            GLib.idle_add(self._on_quick_scan_complete, [], gen)
            return

        # Show scanning state
        self._hero_icon.set_from_icon_name("edit-clear-all-symbolic")
        self._hero_title.set_label("Quick Scanning\u2026")
        self._hero_description.set_label("")
        self._scan_progress.set_visible(True)
        self._scan_spinner.set_spinning(True)
        self._button_box.set_visible(False)
        self._breakdown_group.set_visible(False)

        def do_scan():
            results = self.window.client.scan_streaming(plugin_ids=quick_ids)
            GLib.idle_add(self._on_quick_scan_complete, results, gen)

        threading.Thread(target=do_scan, daemon=True).start()

    def _on_quick_scan_complete(self, results: list[dict], generation: int) -> None:
        """Update the dashboard with quick scan results."""
        if generation != self._scan_generation:
            return

        self._scan_results = results
        self._scan_spinner.set_spinning(False)
        self._scan_progress.set_visible(False)
        self._button_box.set_visible(True)

        total = sum(r["total_bytes"] for r in results)
        module_count = sum(1 for r in results if r["total_bytes"] > 0)

        # Build description with last-clean time
        last_clean = self.window.client.get_last_clean_time()
        last_clean_text = f"Last cleaning {format_relative_time(last_clean)}" if last_clean else ""

        if total > 0:
            self._hero_icon.set_from_icon_name("edit-clear-all-symbolic")
            self._hero_title.set_label(f"{bytes_to_human(total)} Reclaimable")
            self._review_btn.set_visible(True)
            mod_word = "module" if module_count == 1 else "modules"
            mod_text = f"{module_count} {mod_word} found reclaimable space"
            if last_clean_text:
                self._hero_description.set_label(f"{mod_text} \u00b7 {last_clean_text}")
            else:
                self._hero_description.set_label(mod_text)
        else:
            self._hero_icon.set_from_icon_name("emblem-ok-symbolic")
            self._hero_title.set_label("Your System is Clean")
            self._review_btn.set_visible(False)
            self._hero_description.set_label(
                last_clean_text or "Nothing to clean right now"
            )

        self._populate_breakdown(results, total)

    # ── Reclaimable breakdown ──────────────────────────────────

    def _populate_breakdown(self, results: list[dict], grand_total: int) -> None:
        """Populate the reclaimable space breakdown from scan results."""
        for old_row in self._breakdown_rows:
            self._breakdown_group.remove(old_row)
        self._breakdown_rows.clear()
        self._level_bars.clear()
        self._size_labels.clear()

        actionable = [r for r in results if r["total_bytes"] > 0]
        if not actionable:
            self._breakdown_group.set_visible(False)
            return

        self._breakdown_group.set_visible(True)

        # Group by category, then aggregate plugin groups within each
        by_category: dict[str, list[dict]] = {}
        for r in actionable:
            by_category.setdefault(r.get("category", "user"), []).append(r)

        cat_display: dict[str, list[dict]] = {}
        for cat, cat_results in by_category.items():
            items: list[dict] = []
            groups: dict[str, dict] = {}

            for r in cat_results:
                group = r.get("group")
                if group:
                    gid = group["id"]
                    if gid not in groups:
                        groups[gid] = {
                            "name": group["name"],
                            "icon": r.get("icon", "application-x-executable-symbolic"),
                            "total_bytes": 0,
                            "file_count": 0,
                        }
                    groups[gid]["total_bytes"] += r["total_bytes"]
                    groups[gid]["file_count"] += r["file_count"]
                else:
                    items.append({
                        "name": r["plugin_name"],
                        "icon": r.get("icon", "application-x-executable-symbolic"),
                        "total_bytes": r["total_bytes"],
                        "file_count": r["file_count"],
                    })

            items.extend(groups.values())
            cat_display[cat] = items

        # Sort categories by total bytes (descending)
        cat_totals = {
            cat: sum(it["total_bytes"] for it in items)
            for cat, items in cat_display.items()
        }
        sorted_cats = sorted(cat_totals, key=cat_totals.get, reverse=True)

        for cat in sorted_cats:
            items = cat_display[cat]
            total_bytes = cat_totals[cat]
            total_entries = sum(it["file_count"] for it in items)

            cat_row = Adw.ExpanderRow(
                title=CATEGORY_LABELS.get(cat, cat.replace("_", " ").title()),
                subtitle=(
                    f"{bytes_to_human(total_bytes)} \u00b7 "
                    f"{total_entries:,} entr{'ies' if total_entries != 1 else 'y'}"
                ),
            )

            suffix_box = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)

            if grand_total > 0:
                level_bar = Gtk.LevelBar()
                level_bar.set_mode(Gtk.LevelBarMode.CONTINUOUS)
                level_bar.set_min_value(0)
                level_bar.set_max_value(1)
                level_bar.set_value(max(total_bytes / grand_total, 0.02))
                level_bar.set_size_request(48, 6)
                level_bar.set_valign(Gtk.Align.CENTER)
                level_bar.remove_offset_value("low")
                level_bar.remove_offset_value("high")
                level_bar.remove_offset_value("full")
                suffix_box.append(level_bar)
                self._level_bars.append(level_bar)

            size_label = Gtk.Label(label=bytes_to_human(total_bytes))
            size_label.add_css_class("accent")
            size_label.set_width_chars(8)
            size_label.set_xalign(1.0)
            suffix_box.append(size_label)
            self._size_labels.append(size_label)
            cat_row.add_suffix(suffix_box)

            for item in sorted(items, key=lambda x: x["total_bytes"], reverse=True):
                plugin_row = Adw.ActionRow(title=item["name"])
                plugin_row.add_prefix(Gtk.Image.new_from_icon_name(item["icon"]))

                plugin_size = Gtk.Label(label=bytes_to_human(item["total_bytes"]))
                plugin_size.add_css_class("accent")
                plugin_size.set_width_chars(8)
                plugin_size.set_xalign(1.0)
                plugin_row.add_suffix(plugin_size)
                self._size_labels.append(plugin_size)
                cat_row.add_row(plugin_row)

            self._breakdown_group.add(cat_row)
            self._breakdown_rows.append(cat_row)

    # ── Historical stats & cleaning history ───────────────────

    def _refresh_stats(self) -> None:
        """Refresh historical statistics cards and cleaning history."""
        stats_today = self.window.client.get_stats("today")
        stats_week = self.window.client.get_stats("week")
        stats_all = self.window.client.get_stats("all")

        has_data = stats_all["lifetime_bytes_freed"] > 0
        self.stats_box.set_visible(has_data)

        if has_data:
            self.card_today._value_label.set_label(bytes_to_human(stats_today["bytes_freed"]))
            self.card_week._value_label.set_label(bytes_to_human(stats_week["bytes_freed"]))
            self.card_lifetime._value_label.set_label(bytes_to_human(stats_all["lifetime_bytes_freed"]))

        self._populate_history(stats_all)

    def _populate_history(self, stats_all: dict) -> None:
        """Populate the historical per-module cleaning breakdown."""
        for old_row in self._history_rows:
            self._history_group.remove(old_row)
        self._history_rows.clear()

        per_plugin = stats_all.get("per_plugin", {})
        if not per_plugin or not any(s["bytes_freed"] > 0 for s in per_plugin.values()):
            self._history_group.set_visible(False)
            return

        self._history_group.set_visible(True)

        # Aggregate plugin stats by group, then by category
        display_items: list[dict] = []
        group_agg: dict[str, dict] = {}

        for pid, pstats in per_plugin.items():
            if pstats["bytes_freed"] <= 0:
                continue
            info = self._plugin_info.get(pid)
            cat = info.get("category", "system") if info else "system"
            group = info.get("group") if info else None

            if group:
                gid = group["id"]
                if gid not in group_agg:
                    group_agg[gid] = {
                        "name": group["name"],
                        "icon": info.get("icon", "application-x-executable-symbolic") if info else "folder-symbolic",
                        "category": cat,
                        "bytes_freed": 0,
                        "files_removed": 0,
                    }
                group_agg[gid]["bytes_freed"] += pstats["bytes_freed"]
                group_agg[gid]["files_removed"] += pstats["files_removed"]
            else:
                display_items.append({
                    "name": info["name"] if info else pid,
                    "icon": info.get("icon", "application-x-executable-symbolic") if info else "folder-symbolic",
                    "noun": info.get("item_noun", "file") if info else "file",
                    "category": cat,
                    "bytes_freed": pstats["bytes_freed"],
                    "files_removed": pstats["files_removed"],
                })

        for agg in group_agg.values():
            display_items.append({
                "name": agg["name"],
                "icon": agg["icon"],
                "noun": "file",
                "category": agg["category"],
                "bytes_freed": agg["bytes_freed"],
                "files_removed": agg["files_removed"],
            })

        # Group display items by category
        cat_data: dict[str, list[dict]] = {}
        for item in display_items:
            cat_data.setdefault(item["category"], []).append(item)

        # Sort categories by total bytes freed (descending)
        cat_totals = {
            cat: sum(it["bytes_freed"] for it in items)
            for cat, items in cat_data.items()
        }
        sorted_cats = sorted(cat_totals, key=cat_totals.get, reverse=True)

        for cat in sorted_cats:
            items = cat_data[cat]
            total_bytes = cat_totals[cat]
            total_files = sum(it["files_removed"] for it in items)

            cat_row = Adw.ExpanderRow(
                title=CATEGORY_LABELS.get(cat, cat.replace("_", " ").title()),
                subtitle=f"{bytes_to_human(total_bytes)} freed \u2014 {total_files:,} files cleaned",
            )

            size_label = Gtk.Label(label=bytes_to_human(total_bytes))
            size_label.add_css_class("dim-label")
            size_label.set_width_chars(8)
            size_label.set_xalign(1.0)
            cat_row.add_suffix(size_label)

            for item in sorted(items, key=lambda x: x["bytes_freed"], reverse=True):
                count = item["files_removed"]
                noun = item.get("noun", "file")
                label = noun if count == 1 else noun + "s"

                plugin_row = Adw.ActionRow(
                    title=item["name"],
                    subtitle=f"{count:,} {label} cleaned",
                )
                plugin_row.add_prefix(Gtk.Image.new_from_icon_name(item["icon"]))

                plugin_size = Gtk.Label(label=bytes_to_human(item["bytes_freed"]))
                plugin_size.add_css_class("dim-label")
                plugin_size.set_width_chars(8)
                plugin_size.set_xalign(1.0)
                plugin_row.add_suffix(plugin_size)
                cat_row.add_row(plugin_row)

            self._history_group.add(cat_row)
            self._history_rows.append(cat_row)

    # ── Actions ───────────────────────────────────────────────

    def _on_review_clean(self, button: Gtk.Button) -> None:
        """Show quick scan results in the Results view for selective cleaning."""
        results_view = self.window.scan_results_view
        results_view._show_empty_results = False
        results_view._progress_revealer.set_reveal_child(False)
        results_view.populate(self._scan_results)
        self.window.switch_to_results()

    def _on_safe_scan(self, button: Gtk.Button) -> None:
        """Launch a scan with only safe-risk plugins."""
        safe_ids = [
            pid for pid, info in self._plugin_info.items()
            if info["available"] and info["risk_level"] == "safe"
        ]
        self.window.launch_scan(safe_ids)

    def _on_full_scan(self, button: Gtk.Button) -> None:
        """Launch a scan with all available plugins."""
        all_ids = [
            pid for pid, info in self._plugin_info.items()
            if info["available"]
        ]
        self.window.launch_scan(all_ids)

    def refresh(self) -> None:
        """Public method to refresh dashboard data after cleaning."""
        self._refresh_stats()
        self._start_quick_scan()

    # ── Responsive layout ────────────────────────────────────

    def _on_viewport_resize(self, adjustment, pspec) -> None:
        """Switch buttons and stats layout based on viewport width."""
        viewport_width = adjustment.get_page_size()
        if viewport_width >= 500:
            mode = "wide"
        elif viewport_width >= 300:
            mode = "medium"
        else:
            mode = "narrow"
        if mode != self._layout_mode:
            self._layout_mode = mode
            GLib.idle_add(self._apply_responsive_layout)

    def _apply_responsive_layout(self) -> bool:
        """Apply the responsive layout change (called from idle)."""
        H, V = Gtk.Orientation.HORIZONTAL, Gtk.Orientation.VERTICAL
        compact = self._layout_mode != "wide"
        narrow = self._layout_mode == "narrow"

        if self._layout_mode == "wide":
            self._button_box.set_orientation(H)
            self._button_box.set_spacing(12)
            self._secondary_btns.set_orientation(H)
            self._secondary_btns.set_spacing(12)
            self.stats_box.set_orientation(H)
            self.stats_box.set_spacing(12)
        elif self._layout_mode == "medium":
            self._button_box.set_orientation(V)
            self._button_box.set_spacing(8)
            self._secondary_btns.set_orientation(H)
            self._secondary_btns.set_spacing(12)
            self.stats_box.set_orientation(V)
            self.stats_box.set_spacing(8)
        else:
            self._button_box.set_orientation(V)
            self._button_box.set_spacing(8)
            self._secondary_btns.set_orientation(V)
            self._secondary_btns.set_spacing(8)
            self.stats_box.set_orientation(V)
            self.stats_box.set_spacing(8)

        # Reduce margins and hide level bars at compact/narrow widths
        margin = 8 if narrow else 24
        self.content_box.set_margin_start(margin)
        self.content_box.set_margin_end(margin)

        for bar in self._level_bars:
            bar.set_visible(not compact)
        for label in self._size_labels:
            label.set_width_chars(6 if narrow else 8)

        return GLib.SOURCE_REMOVE
