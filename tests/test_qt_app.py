from __future__ import annotations

import unittest

import lvms_stat.qt_app as qt_app
from lvms_stat.qt_app import PyQtUnavailable, load_pyqt6


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

    def test_file_locations_are_visible_before_fetch(self) -> None:
        self.assertTrue(hasattr(qt_app, "file_location_messages"))
        messages = qt_app.file_location_messages(
            r"K:\Statistikk", "solide", r"C:\LVMS-STAT\rådata"
        )

        self.assertEqual(len(messages), 3)
        self.assertIn(r"C:\LVMS-STAT\rådata", messages[0])
        self.assertIn(r"K:\Statistikk\solide\raa", messages[1])
        self.assertIn(r"K:\Statistikk\solide\prosessert", messages[2])


if __name__ == "__main__":
    unittest.main()
