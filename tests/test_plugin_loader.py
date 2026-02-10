"""Tests for plugin discovery and loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from sweep.core.registry import PluginRegistry
from sweep.core.plugin_loader import load_plugins, _find_plugins_in_module


class TestPluginRegistry:
    def test_register_and_get(self):
        from tests.test_engine import FakePlugin

        registry = PluginRegistry()
        plugin = FakePlugin("test")
        registry.register(plugin)

        assert registry.get("test") is plugin
        assert "test" in registry
        assert len(registry) == 1

    def test_duplicate_registration_skipped(self):
        from tests.test_engine import FakePlugin

        registry = PluginRegistry()
        registry.register(FakePlugin("dup"))
        registry.register(FakePlugin("dup"))
        assert len(registry) == 1

    def test_get_by_category(self):
        from tests.test_engine import FakePlugin

        registry = PluginRegistry()
        registry.register(FakePlugin("a"))
        registry.register(FakePlugin("b"))

        user_plugins = registry.get_by_category("user")
        assert len(user_plugins) == 2

    def test_get_available(self):
        from tests.test_engine import FakePlugin

        registry = PluginRegistry()
        registry.register(FakePlugin("avail", available=True))
        registry.register(FakePlugin("not_avail", available=False))

        available = registry.get_available()
        assert len(available) == 1
        assert available[0].id == "avail"


class TestPluginLoader:
    def test_loads_builtin_plugins(self):
        registry = PluginRegistry()
        load_plugins(registry)
        assert len(registry) == 80  # All built-in standalone plugins

    def test_all_plugins_have_unique_ids(self):
        registry = PluginRegistry()
        load_plugins(registry)
        ids = [p.id for p in registry]
        assert len(ids) == len(set(ids))
