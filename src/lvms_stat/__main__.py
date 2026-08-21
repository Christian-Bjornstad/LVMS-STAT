from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path

from lvms_stat.batch_runner import run_report_batch
from lvms_stat.probe import run_doctor, run_probe
from lvms_stat.report_runner import discover_report, run_report_job
from lvms_stat.tk_app import run_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lvms-stat",
        description="Supervised, privacy-safe LVMS Edge connectivity tools.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("doctor", "Return one fixed managed Edge and LVMS capability result."),
        ("probe", "Open Edge and verify only the configured LVMS origin."),
        ("inspect", "After confirmation, list sanitized fixed page controls."),
        ("app", "Open the supervised safe workflow recorder window."),
    ):
        command_parser = subcommands.add_parser(command, help=help_text)
        command_parser.add_argument(
            "--config",
            type=Path,
            required=True,
            help="Path to the ignored local config.json file.",
        )

    discover_parser = subcommands.add_parser(
        "discover-report", help="Save a sanitized defined-report field contract."
    )
    discover_parser.add_argument("--config", type=Path, required=True)

    run_parser = subcommands.add_parser(
        "run-job", help="Populate and explicitly export one local report job."
    )
    run_parser.add_argument("--config", type=Path, required=True)
    run_parser.add_argument("--jobs", type=Path, required=True)
    run_parser.add_argument("--contract", type=Path, required=True)
    run_parser.add_argument("--job", dest="job_key", required=True)

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
    probe_runner: Callable[..., int] = run_probe,
    doctor_runner: Callable[[Path], int] = run_doctor,
    app_runner: Callable[[Path], int] = run_app,
    discover_runner: Callable[[Path], int] = discover_report,
    report_runner: Callable[[Path, Path, Path, str], int] = run_report_job,
    batch_runner: Callable[[Path, Path, tuple[str, ...]], int] = run_report_batch,
) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.command == "doctor":
        return doctor_runner(arguments.config)
    if arguments.command == "app":
        return app_runner(arguments.config)
    if arguments.command == "discover-report":
        return discover_runner(arguments.config)
    if arguments.command == "run-job":
        return report_runner(
            arguments.config, arguments.jobs, arguments.contract, arguments.job_key
        )
    if arguments.command == "run-batch":
        return batch_runner(
            arguments.config, arguments.jobs, tuple(arguments.job_keys)
        )
    return probe_runner(arguments.config, inspect=arguments.command == "inspect")


if __name__ == "__main__":
    raise SystemExit(main())
