from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path

from lvms_stat.batch_runner import run_report_batch
from lvms_stat.qt_app import run_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lvms-stat",
        description="Visible LVMS three-report automation.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    app_parser = subcommands.add_parser(
        "app", help="Open the one-click PyQt6 three-report window."
    )
    app_parser.add_argument("--config", type=Path, required=True)

    batch_parser = subcommands.add_parser(
        "run-batch", help="Automatically export three explicit local report jobs."
    )
    batch_parser.add_argument("--config", type=Path, required=True)
    batch_parser.add_argument("--jobs", type=Path, required=True)
    batch_parser.add_argument(
        "--job", dest="job_keys", action="append", required=True
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    app_runner: Callable[[Path], int] = run_app,
    batch_runner: Callable[[Path, Path, tuple[str, ...]], int] = run_report_batch,
) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.command == "app":
        return app_runner(arguments.config)
    return batch_runner(arguments.config, arguments.jobs, tuple(arguments.job_keys))


if __name__ == "__main__":
    raise SystemExit(main())
