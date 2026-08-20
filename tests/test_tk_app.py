from __future__ import annotations

import unittest

from lvms_stat.tk_app import TkUnavailable, format_step, load_tkinter
from lvms_stat.workflow import ControlIdentity, ParameterRole, StepKind, WorkflowStep


class TkAppTests(unittest.TestCase):
    def test_load_tkinter_uses_injected_importer_and_sanitizes_failure(self) -> None:
        modules = {name: object() for name in ("tkinter", "tkinter.ttk", "tkinter.messagebox")}
        self.assertEqual(load_tkinter(importer=modules.__getitem__), tuple(modules.values()))
        with self.assertRaises(TkUnavailable) as caught:
            load_tkinter(importer=lambda name: (_ for _ in ()).throw(ImportError("detail")))
        self.assertNotIn("detail", str(caught.exception))

    def test_formats_parameter_without_value_or_unsafe_label(self) -> None:
        field = WorkflowStep(
            3,
            StepKind.FIELD_EDITED,
            ControlIdentity("INPUT", label="From date"),
            ParameterRole.FROM_DATE,
        )
        self.assertEqual(format_step(field), "3. Edit field: From date [value not recorded]")
        unsafe = WorkflowStep(
            4, StepKind.ACTIVATE, ControlIdentity("A", label="https://x.invalid/report.csv")
        )
        rendered = format_step(unsafe)
        self.assertNotIn("https://", rendered)
        self.assertNotIn(".csv", rendered)


if __name__ == "__main__":
    unittest.main()
