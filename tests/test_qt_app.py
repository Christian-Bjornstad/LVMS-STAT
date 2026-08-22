from __future__ import annotations

import unittest
from pathlib import Path

from lvms_stat.qt_app import (
    DEFAULT_JOB_KEYS,
    PyQtUnavailable,
    load_pyqt6,
    run_one_click_batch,
)


class QtAppTests(unittest.TestCase):
    def test_load_pyqt6_sanitizes_import_failure(self) -> None:
        modules = {name: object() for name in ("PyQt6.QtCore", "PyQt6.QtWidgets")}

        self.assertEqual(load_pyqt6(importer=modules.__getitem__), tuple(modules.values()))

        with self.assertRaises(PyQtUnavailable) as caught:
            load_pyqt6(
                importer=lambda name: (_ for _ in ()).throw(
                    ImportError("internal installation detail")
                )
            )
        self.assertNotIn("internal installation detail", str(caught.exception))

    def test_one_click_batch_uses_sibling_jobs_and_fixed_three_job_order(self) -> None:
        calls: list[tuple[Path, Path, tuple[str, ...]]] = []
        statuses: list[str] = []

        result = run_one_click_batch(
            Path("local/config.json"),
            runner=lambda config, jobs, keys, progress, failure: calls.append(
                (config, jobs, keys)
            )
            or progress(1, 3)
            or progress(2, 3)
            or progress(3, 3)
            or 0,
            status=statuses.append,
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            calls,
            [
                (
                    Path("local/config.json"),
                    Path("local/jobs.hematology-test.json"),
                    DEFAULT_JOB_KEYS,
                )
            ],
        )
        self.assertEqual(
            statuses,
            [
                "Åpner LVMS og starter rapportene …",
                "Kjører rapport 1 av 3 …",
                "Kjører rapport 2 av 3 …",
                "Kjører rapport 3 av 3 …",
                "Ferdig – 3 rapporter er lastet ned.",
            ],
        )

    def test_one_click_batch_reports_fixed_failure_without_retry(self) -> None:
        calls = 0
        statuses: list[str] = []

        def fail(
            config: Path,
            jobs: Path,
            keys: tuple[str, ...],
            progress: object,
            failure: object,
        ) -> int:
            nonlocal calls
            del config, jobs, keys, progress, failure
            calls += 1
            return 2

        result = run_one_click_batch(
            Path("config.json"), runner=fail, status=statuses.append
        )

        self.assertEqual(result, 2)
        self.assertEqual(calls, 1)
        self.assertEqual(
            statuses[-1], "Kjøringen stoppet. Rett feilen og prøv igjen manuelt."
        )

    def test_one_click_batch_reports_sanitized_failure_stage(self) -> None:
        statuses: list[str] = []

        def fail(
            config: Path,
            jobs: Path,
            keys: tuple[str, ...],
            progress: object,
            failure: object,
        ) -> int:
            del config, jobs, keys, progress
            failure("lvms_open")  # type: ignore[operator]
            return 2

        result = run_one_click_batch(
            Path("config.json"), runner=fail, status=statuses.append
        )

        self.assertEqual(result, 2)
        self.assertEqual(statuses[-1], "Kjøringen stoppet ved: åpning av LVMS.")

    def test_one_click_batch_reports_navigation_substage(self) -> None:
        statuses: list[str] = []

        def fail(config, jobs, keys, progress, failure):  # type: ignore[no-untyped-def]
            del config, jobs, keys, progress
            failure("defined_reports_wait_form")
            return 2

        run_one_click_batch(Path("config.json"), runner=fail, status=statuses.append)

        self.assertEqual(
            statuses[-1],
            "Kjøringen stoppet ved: venting på rapportskjemaet etter klikk.",
        )


if __name__ == "__main__":
    unittest.main()
