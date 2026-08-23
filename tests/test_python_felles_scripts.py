from __future__ import annotations

import runpy
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PythonFellesScriptTests(unittest.TestCase):
    def test_installer_uses_current_project_and_verifies_required_imports(self) -> None:
        functions = runpy.run_path(str(ROOT / "install_python_felles.py"))
        calls: list[list[str]] = []
        imported: list[str] = []

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            (project / "src" / "lvms_stat").mkdir(parents=True)
            result = functions["install"](
                project_dir=project,
                user_site=project / "user-site",
                pip_main=lambda args: calls.append(list(args)) or 0,
                importer=lambda name: imported.append(name) or object(),
            )
            installed_from_project = Path(calls[0][-1]).samefile(project)

        self.assertEqual(result, 0)
        self.assertTrue(installed_from_project)
        self.assertEqual(imported, ["PyQt6", "websocket", "lvms_stat"])

    def test_start_script_needs_no_local_json_files_and_dispatches_app(self) -> None:
        functions = runpy.run_path(str(ROOT / "start_python_felles.py"))
        calls: list[list[str]] = []

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "src" / "lvms_stat").mkdir(parents=True)
            result = functions["start"](
                project_dir=project,
                user_site=project / "user-site",
                app_main=lambda args: calls.append(list(args)) or 0,
            )

        self.assertEqual(result, 0)
        self.assertEqual(calls, [["app"]])


if __name__ == "__main__":
    unittest.main()
