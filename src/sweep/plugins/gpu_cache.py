"""Plugins to clean GPU cache directories (shader and compute)."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup, SimpleCacheDirPlugin
from sweep.utils import xdg_cache_home

_GROUP = PluginGroup("gpu", "GPU Cache", "Compiled shader and compute caches from GPU drivers")


class NvidiaShaderCachePlugin(SimpleCacheDirPlugin):
    """Cleans NVIDIA shader cache."""

    @property
    def id(self) -> str:
        return "nvidia_shader_cache"

    @property
    def name(self) -> str:
        return "NVIDIA Shader"

    @property
    def description(self) -> str:
        return "NVIDIA shader cache"

    @property
    def category(self) -> str:
        return "user"

    @property
    def risk_level(self) -> str:
        return "moderate"

    @property
    def icon(self) -> str:
        return "video-display-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dir_name(self) -> str:
        return "nvidia"

    @property
    def _label(self) -> str:
        return "NVIDIA Shader"


class NvidiaComputeCachePlugin(MultiDirPlugin):
    """Cleans NVIDIA CUDA compute cache."""

    @property
    def id(self) -> str:
        return "nvidia_compute_cache"

    @property
    def name(self) -> str:
        return "NVIDIA Compute"

    @property
    def description(self) -> str:
        return "NVIDIA CUDA compute cache"

    @property
    def category(self) -> str:
        return "user"

    @property
    def risk_level(self) -> str:
        return "moderate"

    @property
    def icon(self) -> str:
        return "video-display-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".nv" / "ComputeCache",)


class MesaShaderCachePlugin(MultiDirPlugin):
    """Cleans Mesa shader cache."""

    @property
    def id(self) -> str:
        return "mesa_shader_cache"

    @property
    def name(self) -> str:
        return "Mesa"

    @property
    def description(self) -> str:
        return "Mesa shader cache"

    @property
    def category(self) -> str:
        return "user"

    @property
    def risk_level(self) -> str:
        return "moderate"

    @property
    def icon(self) -> str:
        return "video-display-symbolic"

    @property
    def group(self):
        return _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        cache = xdg_cache_home()
        return (cache / "mesa_shader_cache", cache / "mesa_shader_cache_db")
