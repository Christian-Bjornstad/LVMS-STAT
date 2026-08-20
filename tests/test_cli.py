from __future__ import annotations

import unittest
from pathlib import Path

from lvms_stat.__main__ import build_parser, main


class CliTests(unittest.TestCase):
    def test_parser_exposes_probe_and_inspect_commands(self) -> None:
        parser = build_parser()

        probe = parser.parse_args(["probe", "--config", "config.json"])
        inspect = parser.parse_args(["inspect", "--config", "config.json"])

        self.assertEqual(probe.command, "probe")
        self.assertEqual(inspect.command, "inspect")

    def test_main_passes_explicit_inspection_mode_to_runner(self) -> None:
        calls: list[tuple[Path, bool]] = []

        def runner(config_path: Path, *, inspect: bool) -> int:
            calls.append((config_path, inspect))
            return 7

        result = main(["inspect", "--config", "safe.json"], runner=runner)

        self.assertEqual(result, 7)
        self.assertEqual(calls, [(Path("safe.json"), True)])


if __name__ == "__main__":
    unittest.main()
