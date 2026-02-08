"""Privilege escalation via pkexec for root-requiring plugins."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess

log = logging.getLogger(__name__)

# Timeout for the pkexec subprocess (seconds).
_PKEXEC_TIMEOUT = 300


class PrivilegeError(Exception):
    """Raised when privilege escalation fails."""


def is_root() -> bool:
    """Check if the current process is running as root."""
    return os.geteuid() == 0


def find_sweep_executable() -> str | None:
    """Find the sweep CLI executable on PATH."""
    return shutil.which("sweep")


def pkexec_available() -> bool:
    """Check if pkexec is available on the system."""
    return shutil.which("pkexec") is not None


def run_privileged_clean(entries_by_plugin: dict[str, list[dict]]) -> list[dict]:
    """Run a privileged clean operation via pkexec.

    Serializes *entries_by_plugin* as JSON on stdin, invokes
    ``pkexec sweep clean-as-root``, and parses the JSON results from stdout.

    Args:
        entries_by_plugin: Mapping of plugin_id to list of entry dicts
            (each with 'path', 'size_bytes').

    Returns:
        List of result dicts (plugin_id, freed_bytes, files_removed, errors).

    Raises:
        PrivilegeError: On authentication cancel/deny/timeout/bad output.
    """
    sweep_exe = find_sweep_executable()
    if sweep_exe is None:
        raise PrivilegeError("Could not find the 'sweep' executable on PATH")

    payload = json.dumps({"entries_by_plugin": entries_by_plugin})

    try:
        proc = subprocess.run(
            ["pkexec", sweep_exe, "clean-as-root"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=_PKEXEC_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise PrivilegeError("Privileged clean timed out after 5 minutes")

    if proc.returncode == 126:
        raise PrivilegeError("Authentication dismissed by user")
    if proc.returncode == 127:
        raise PrivilegeError("Authentication denied")
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        raise PrivilegeError(f"Privileged clean failed (exit {proc.returncode}): {stderr}")

    try:
        return json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise PrivilegeError(f"Invalid response from privileged process: {exc}")
