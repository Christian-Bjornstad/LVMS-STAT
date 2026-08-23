from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path

from lvms_stat import __version__
from lvms_stat.batch_runner import run_report_batch
from lvms_stat.qt_app import run_app
from lvms_stat.settings_store import settings_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lvms-stat",
        description="Visible LVMS statistics automation.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"lvms-stat {__version__}",
        help="Show the installed version and exit.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    app_parser = subcommands.add_parser(
        "app", help="Open the statistics dashboard window."
    )
    app_parser.add_argument(
        "--config",
        type=Path,
        help=(
            "Optional configuration file. Defaults to the app-managed "
            "settings under Local AppData."
        ),
    )

    batch_parser = subcommands.add_parser(
        "run-batch", help="Automatically export explicit local report jobs."
    )
    batch_parser.add_argument("--config", type=Path, required=True)
    batch_parser.add_argument("--jobs", type=Path, required=True)
    batch_parser.add_argument(
        "--job", dest="job_keys", action="append", required=True
    )

    auto_parser = subcommands.add_parser(
        "auto",
        help="Headless scheduled incremental fetch of every unit; exits when done.",
    )
    auto_parser.add_argument("--config", type=Path, required=True)
    auto_parser.add_argument(
        "--unit",
        dest="unit_keys",
        action="append",
        help="Limit the run to specific unit keys (repeatable).",
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    app_runner: Callable[[Path], int] = run_app,
    batch_runner: Callable[[Path, Path, tuple[str, ...]], int] = run_report_batch,
    scheduled_runner: Callable[..., int] | None = None,
) -> int:
    from lvms_stat.scheduled import run_scheduled

    runner = scheduled_runner or run_scheduled
    arguments = build_parser().parse_args(argv)
    if arguments.command == "app":
        return app_runner(arguments.config or settings_path())
    if arguments.command == "auto":
        return runner(
            arguments.config,
            unit_keys=(
                tuple(arguments.unit_keys) if arguments.unit_keys else None
            ),
        )
    return batch_runner(arguments.config, arguments.jobs, tuple(arguments.job_keys))


if __name__ == "__main__":
    raise SystemExit(main())
