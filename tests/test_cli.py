from __future__ import annotations

import unittest
from pathlib import Path

from lvms_stat.__main__ import build_parser, main


class CliTests(unittest.TestCase):
    def test_parser_exposes_probe_inspect_and_app_commands(self) -> None:
        parser = build_parser()

        probe = parser.parse_args(["probe", "--config", "config.json"])
        inspect = parser.parse_args(["inspect", "--config", "config.json"])
        app = parser.parse_args(["app", "--config", "config.json"])

        self.assertEqual(probe.command, "probe")
        self.assertEqual(inspect.command, "inspect")
        self.assertEqual(app.command, "app")

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


if __name__ == "__main__":
    unittest.main()
