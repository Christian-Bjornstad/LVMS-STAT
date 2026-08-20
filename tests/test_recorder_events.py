from __future__ import annotations

import unittest

from lvms_stat.recorder_events import (
    RECORDER_INSTALL_SCRIPT_TEMPLATE,
    RecorderEventError,
    sanitize_event_batch,
)
from lvms_stat.workflow import StepKind


class RecorderEventTests(unittest.TestCase):
    def candidate(self, **changes: object) -> dict[str, object]:
        candidate: dict[str, object] = {
            "nonce": "safe-nonce",
            "kind": "activate",
            "control": {
                "tag": "BUTTON",
                "type": "button",
                "id": "export",
                "name": "",
                "role": "button",
                "label": "Export",
                "locator": ["button#export"],
            },
        }
        candidate.update(changes)
        return candidate

    def test_sanitizes_allowlisted_activation(self) -> None:
        steps = sanitize_event_batch(
            [self.candidate()], start_step_id=3, expected_nonce="safe-nonce"
        )
        self.assertEqual(steps[0].step_id, 3)
        self.assertEqual(steps[0].kind, StepKind.ACTIVATE)
        self.assertEqual(steps[0].control.label, "Export")

    def test_rejects_unknown_forbidden_nonce_and_unsafe_controls(self) -> None:
        invalid = (
            self.candidate(extra="x"),
            self.candidate(value="secret"),
            self.candidate(nonce="late"),
            self.candidate(control={**self.candidate()["control"], "value": "secret"}),
            self.candidate(control={**self.candidate()["control"], "type": "password"}),
            self.candidate(control={**self.candidate()["control"], "locator": ["x"] * 13}),
        )
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaises(RecorderEventError):
                    sanitize_event_batch(
                        [candidate], start_step_id=1, expected_nonce="safe-nonce"
                    )

    def test_caps_batch_and_truncates_strings(self) -> None:
        with self.assertRaises(RecorderEventError):
            sanitize_event_batch(
                [self.candidate()] * 101,
                start_step_id=1,
                expected_nonce="safe-nonce",
            )
        long = self.candidate(
            control={**self.candidate()["control"], "label": "A" * 200}
        )
        step = sanitize_event_batch(
            [long], start_step_id=1, expected_nonce="safe-nonce"
        )[0]
        self.assertEqual(len(step.control.label), 120)

    def test_listener_source_avoids_sensitive_properties(self) -> None:
        for forbidden in (
            ".value",
            "document.cookie",
            "localStorage",
            "sessionStorage",
            "clipboardData",
            "innerHTML",
            "outerHTML",
            "performance.getEntries",
        ):
            self.assertNotIn(forbidden, RECORDER_INSTALL_SCRIPT_TEMPLATE)
        for exclusion in ("table", "treegrid", "password", "hidden", "contenteditable"):
            self.assertIn(exclusion, RECORDER_INSTALL_SCRIPT_TEMPLATE.lower())

    def test_listener_marks_only_actually_edited_fields(self) -> None:
        self.assertIn("new WeakSet", RECORDER_INSTALL_SCRIPT_TEMPLATE)
        self.assertIn('addEventListener("input"', RECORDER_INSTALL_SCRIPT_TEMPLATE)
        self.assertIn("edited.has(el)", RECORDER_INSTALL_SCRIPT_TEMPLATE)
        self.assertIn("activationTypes", RECORDER_INSTALL_SCRIPT_TEMPLATE)


if __name__ == "__main__":
    unittest.main()
