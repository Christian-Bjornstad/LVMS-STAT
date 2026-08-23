"""Stable, zero-argument launcher for portals such as eMolPat."""

from __future__ import annotations

from lvms_stat.__main__ import main as cli_main


def main() -> int:
    """Launch the GUI with its app-managed Local AppData settings."""
    return cli_main(["app"])
