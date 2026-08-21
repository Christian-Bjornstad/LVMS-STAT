from __future__ import annotations

import unittest
from pathlib import Path

from lvms_stat.__main__ import build_parser, main


class CliTests(unittest.TestCase):
    def test_help_exposes_supervised_gates_without_real_environment_values(self) -> None:
        help_text = build_parser().format_help()

        for command in ("doctor", "discover-report", "run-job"):
            self.assertIn(command, help_text)
        for forbidden in ("internal.example", "REAL_APP_ID", "JSESSIONID"):
            self.assertNotIn(forbidden, help_text)

    def test_parser_exposes_probe_inspect_app_and_report_commands(self) -> None:
        parser = build_parser()

        probe = parser.parse_args(["probe", "--config", "config.json"])
        inspect = parser.parse_args(["inspect", "--config", "config.json"])
        app = parser.parse_args(["app", "--config", "config.json"])
        discover = parser.parse_args(["discover-report", "--config", "config.json"])
        run = parser.parse_args(
            [
                "run-job", "--config", "config.json", "--jobs", "jobs.json",
                "--contract", "contract.json", "--job", "weekly",
            ]
        )

        self.assertEqual(probe.command, "probe")
        self.assertEqual(inspect.command, "inspect")
        self.assertEqual(app.command, "app")
        self.assertEqual(discover.command, "discover-report")
        self.assertEqual(run.job_key, "weekly")

    def test_main_passes_explicit_inspection_mode_to_runner(self) -> None:
        calls: list[tuple[Path, bool]] = []

        def runner(config_path: Path, *, inspect: bool) -> int:
            calls.append((config_path, inspect))
            return 7

        result = main(["inspect", "--config", "safe.json"], probe_runner=runner)

        self.assertEqual(result, 7)
        self.assertEqual(calls, [(Path("safe.json"), True)])

    def test_main_dispatches_app_to_separate_runner(self) -> None:
        calls: list[Path] = []
        result = main(
            ["app", "--config", "safe.json"],
            app_runner=lambda path: calls.append(path) or 9,
        )
        self.assertEqual(result, 9)
        self.assertEqual(calls, [Path("safe.json")])

    def test_main_dispatches_report_commands(self) -> None:
        discover_calls: list[Path] = []
        run_calls: list[tuple[Path, Path, Path, str]] = []

        discovered = main(
            ["discover-report", "--config", "safe.json"],
            discover_runner=lambda path: discover_calls.append(path) or 5,
        )
        ran = main(
            [
                "run-job", "--config", "safe.json", "--jobs", "jobs.json",
                "--contract", "contract.json", "--job", "weekly",
            ],
            report_runner=lambda *args: run_calls.append(args) or 6,
        )

        self.assertEqual(discovered, 5)
        self.assertEqual(ran, 6)
        self.assertEqual(discover_calls, [Path("safe.json")])
        self.assertEqual(
            run_calls,
            [(Path("safe.json"), Path("jobs.json"), Path("contract.json"), "weekly")],
        )

    def test_run_batch_dispatches_three_repeatable_job_keys_in_order(self) -> None:
        calls: list[tuple[Path, Path, tuple[str, ...]]] = []

        result = main(
            [
                "run-batch",
                "--config",
                "config.json",
                "--jobs",
                "jobs.json",
                "--job",
                "ordered",
                "--job",
                "answered",
                "--job",
                "extraction",
            ],
            batch_runner=lambda config, jobs, keys: calls.append(
                (config, jobs, keys)
            )
            or 7,
        )

        self.assertEqual(result, 7)
        self.assertEqual(
            calls,
            [
                (
                    Path("config.json"),
                    Path("jobs.json"),
                    ("ordered", "answered", "extraction"),
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
