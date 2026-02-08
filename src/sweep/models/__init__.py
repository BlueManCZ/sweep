"""Sweep data models."""

from sweep.models.plugin import CleanPlugin, MultiDirPlugin, PluginGroup, SimpleCacheDirPlugin
from sweep.models.scan_result import FileEntry, ScanResult
from sweep.models.clean_result import CleanResult

__all__ = [
    "CleanPlugin",
    "CleanResult",
    "FileEntry",
    "MultiDirPlugin",
    "PluginGroup",
    "ScanResult",
    "SimpleCacheDirPlugin",
]
