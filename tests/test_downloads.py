from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lvms_stat.downloads import (
    CsvArrivalDetector,
    DownloadError,
    DownloadStatus,
    open_local,
)


class DownloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_ignores_existing_and_requires_two_stable_polls(self) -> None:
        (self.root / "existing.csv").write_text("old", encoding="utf-8")
        detector = CsvArrivalDetector(self.root)
        detector.start()
        new = self.root / "new.CSV"
        new.write_text("new", encoding="utf-8")
        self.assertEqual(detector.poll(), DownloadStatus.WAITING)
        self.assertEqual(detector.poll(), DownloadStatus.DETECTED)
        self.assertEqual(detector.detected_path(), new.resolve())

    def test_reports_ambiguity_and_missing_detected_file(self) -> None:
        detector = CsvArrivalDetector(self.root)
        detector.start()
        first = self.root / "one.csv"
        second = self.root / "two.csv"
        first.write_text("1", encoding="utf-8")
        second.write_text("2", encoding="utf-8")
        self.assertEqual(detector.poll(), DownloadStatus.AMBIGUOUS)

        second.unlink()
        self.assertEqual(detector.poll(), DownloadStatus.WAITING)
        self.assertEqual(detector.poll(), DownloadStatus.DETECTED)
        first.unlink()
        self.assertEqual(detector.poll(), DownloadStatus.MISSING)

    def test_open_local_uses_injected_opener_without_reading(self) -> None:
        csv = self.root / "report.csv"
        csv.write_text("synthetic", encoding="utf-8")
        opened: list[str] = []
        open_local(csv, opener=opened.append)
        self.assertEqual(opened, [str(csv)])

    def test_rejects_unsafe_open_targets_and_relative_detector(self) -> None:
        with self.assertRaises(DownloadError):
            CsvArrivalDetector(Path("relative"))
        invalid = (self.root / "missing.csv", self.root / "folder.csv")
        invalid[1].mkdir()
        for path in invalid:
            with self.subTest(path=path):
                with self.assertRaises(DownloadError) as caught:
                    open_local(path, opener=lambda value: None)
                self.assertNotIn(str(path), str(caught.exception))

    def test_waits_while_temporary_download_exists(self) -> None:
        detector = CsvArrivalDetector(self.root)
        detector.start()
        temporary = self.root / "report.csv.crdownload"
        completed = self.root / "report.csv"
        temporary.write_bytes(b"partial")
        completed.write_bytes(b"partial")

        self.assertEqual(detector.poll(), DownloadStatus.WAITING)
        temporary.unlink()
        self.assertEqual(detector.poll(), DownloadStatus.WAITING)
        self.assertEqual(detector.poll(), DownloadStatus.DETECTED)

    def test_rejects_unexpected_non_csv_file(self) -> None:
        detector = CsvArrivalDetector(self.root)
        detector.start()
        (self.root / "unexpected.pdf").write_bytes(b"not a report csv")
        (self.root / "report.csv").write_bytes(b"synthetic")

        self.assertEqual(detector.poll(), DownloadStatus.AMBIGUOUS)


if __name__ == "__main__":
    unittest.main()
