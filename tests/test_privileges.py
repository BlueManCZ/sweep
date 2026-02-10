"""Tests for privilege escalation helpers."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import pytest

from sweep.core.privileges import (
    PrivilegeError,
    find_sweep_executable,
    pkexec_available,
    run_privileged_clean,
)


class TestFindSweepExecutable:
    def test_found(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/sweep" if name == "sweep" else None)
        assert find_sweep_executable() == "/usr/bin/sweep"

    def test_not_found(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: None)
        assert find_sweep_executable() is None


class TestPkexecAvailable:
    def test_available(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/pkexec" if name == "pkexec" else None)
        assert pkexec_available() is True

    def test_not_available(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: None)
        assert pkexec_available() is False


class TestRunPrivilegedClean:
    ENTRIES = {"coredumps": [{"path": "/var/lib/systemd/coredump/core.1", "size_bytes": 4096, "submodule_id": ""}]}
    RESULTS = [{"plugin_id": "coredumps", "freed_bytes": 4096, "files_removed": 1, "errors": []}]

    def test_success(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        with patch("sweep.core.privileges.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(self.RESULTS), stderr=""
            )
            result = run_privileged_clean(self.ENTRIES)

        assert result == self.RESULTS
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][0] == ["pkexec", "/usr/bin/sweep", "clean-as-root"]

    def test_user_cancel(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        with patch("sweep.core.privileges.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=126, stdout="", stderr="")
            with pytest.raises(PrivilegeError, match="dismissed by user"):
                run_privileged_clean(self.ENTRIES)

    def test_auth_denied(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        with patch("sweep.core.privileges.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=127, stdout="", stderr="")
            with pytest.raises(PrivilegeError, match="denied"):
                run_privileged_clean(self.ENTRIES)

    def test_timeout(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        with patch("sweep.core.privileges.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="pkexec", timeout=300)
            with pytest.raises(PrivilegeError, match="timed out"):
                run_privileged_clean(self.ENTRIES)

    def test_bad_json(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        with patch("sweep.core.privileges.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="not json", stderr="")
            with pytest.raises(PrivilegeError, match="Invalid response"):
                run_privileged_clean(self.ENTRIES)

    def test_sweep_not_found(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: None)
        with pytest.raises(PrivilegeError, match="Could not find"):
            run_privileged_clean(self.ENTRIES)

    def test_nonzero_exit(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        with patch("sweep.core.privileges.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="some error")
            with pytest.raises(PrivilegeError, match="exit 1"):
                run_privileged_clean(self.ENTRIES)
