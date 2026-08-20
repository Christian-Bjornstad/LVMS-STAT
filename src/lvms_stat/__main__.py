from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path

from lvms_stat.probe import run_probe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lvms-stat",
        description="Supervised, privacy-safe LVMS Edge connectivity tools.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("probe", "Open Edge and verify only the configured LVMS origin."),
        ("inspect", "After confirmation, list sanitized fixed page controls."),
    ):
        command_parser = subcommands.add_parser(command, help=help_text)
        command_parser.add_argument(
            "--config",
            type=Path,
            required=True,
            help="Path to the ignored local config.json file.",
        )

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Callable[..., int] = run_probe,
) -> int:
    arguments = build_parser().parse_args(argv)
    return runner(arguments.config, inspect=arguments.command == "inspect")


if __name__ == "__main__":
    raise SystemExit(main())
