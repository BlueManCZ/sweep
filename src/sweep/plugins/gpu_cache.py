"""Plugins to clean GPU cache directories (shader and compute)."""

from __future__ import annotations

from pathlib import Path

from sweep.models.plugin import MultiDirPlugin, PluginGroup, SimpleCacheDirPlugin
from sweep.utils import xdg_cache_home

_GROUP = PluginGroup("gpu", "GPU Cache", "Compiled shader and compute caches from GPU drivers")


class NvidiaShaderCachePlugin(SimpleCacheDirPlugin):
    """Cleans NVIDIA shader cache."""

    id = "nvidia_shader_cache"
    name = "NVIDIA Shader"
    description = "NVIDIA shader cache"
    category = "user"
    risk_level = "moderate"
    icon = "video-display-symbolic"
    group = _GROUP
    _cache_dir_name = "nvidia"


class NvidiaComputeCachePlugin(MultiDirPlugin):
    """Cleans NVIDIA CUDA compute cache."""

    id = "nvidia_compute_cache"
    name = "NVIDIA Compute"
    description = "NVIDIA CUDA compute cache"
    category = "user"
    risk_level = "moderate"
    icon = "video-display-symbolic"
    group = _GROUP
    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        return (Path.home() / ".nv" / "ComputeCache",)


class MesaShaderCachePlugin(MultiDirPlugin):
    """Cleans Mesa shader cache."""

    id = "mesa_shader_cache"
    name = "Mesa"
    description = "Mesa shader cache"
    category = "user"
    risk_level = "moderate"
    icon = "video-display-symbolic"
    group = _GROUP

    @property
    def _cache_dirs(self) -> tuple[Path, ...]:
        cache = xdg_cache_home()
        return (cache / "mesa_shader_cache", cache / "mesa_shader_cache_db")
