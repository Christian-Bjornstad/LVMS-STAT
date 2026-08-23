from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
