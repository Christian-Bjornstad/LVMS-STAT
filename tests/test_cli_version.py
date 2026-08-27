"""Task 7: the work-computer guide promises `python -m lvms_stat
--version`; the CLI must deliver it, reporting the release version."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_version_constant_is_release_version() -> None:
    import lvms_stat

    assert lvms_stat.__version__ == "2.0.1"


def test_cli_reports_version() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "lvms_stat", "--version"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert proc.returncode == 0, proc.stderr
    assert "2.0.1" in proc.stdout


def test_cli_rejects_unknown_command() -> None:
    with pytest.raises(SystemExit):
        from lvms_stat.__main__ import main

        main(["--help"])
