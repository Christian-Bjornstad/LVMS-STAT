from __future__ import annotations

import unittest
from pathlib import Path

from lvms_stat.__main__ import build_parser, main


class CliTests(unittest.TestCase):
    def test_help_exposes_only_app_and_batch_without_environment_values(self) -> None:
        help_text = build_parser().format_help()

        for command in ("app", "run-batch"):
            self.assertIn(command, help_text)
        for removed in ("doctor", "probe", "inspect", "discover-report", "run-job"):
            self.assertNotIn(removed, help_text)
        for forbidden in (
            "internal.example", "REAL_APP_ID", "JSESSIONID", "sykehuspartner", "PAT-DIT"
        ):
            self.assertNotIn(forbidden, help_text)

    def test_main_dispatches_app_to_separate_runner(self) -> None:
        calls: list[Path] = []
        result = main(
            ["app", "--config", "safe.json"],
            app_runner=lambda path: calls.append(path) or 9,
        )
        self.assertEqual(result, 9)
        self.assertEqual(calls, [Path("safe.json")])

    def test_run_batch_dispatches_three_repeatable_job_keys_in_order(self) -> None:
        calls: list[tuple[Path, Path, tuple[str, ...]]] = []
        result = main(
            [
                "run-batch", "--config", "config.json", "--jobs", "jobs.json",
                "--job", "ordered", "--job", "answered", "--job", "extraction",
            ],
            batch_runner=lambda config, jobs, keys: calls.append(
                (config, jobs, keys)
            ) or 7,
        )

        self.assertEqual(result, 7)
        self.assertEqual(
            calls,
            [(Path("config.json"), Path("jobs.json"), ("ordered", "answered", "extraction"))],
        )


if __name__ == "__main__":
    unittest.main()
