from __future__ import annotations

import unittest

from lvms_stat.inspection import (
    CONTROL_INSPECTION_SCRIPT,
    InspectionError,
    sanitize_controls,
)


class InspectionTests(unittest.TestCase):
    def test_allowlists_metadata_and_truncates_text(self) -> None:
        result = sanitize_controls(
            [
                {
                    "tag": "BUTTON",
                    "id": "export",
                    "text": "X" * 200,
                    "unexpected": "discarded",
                }
            ],
            max_text_length=12,
        )

        self.assertEqual(
            result,
            [{"tag": "BUTTON", "id": "export", "text": "XXXXXXXXXXXX"}],
        )

    def test_rejects_payload_containing_forbidden_fields(self) -> None:
        for forbidden_field in (
            "value",
            "href",
            "src",
            "cookie",
            "token",
            "authorization",
        ):
            with self.subTest(forbidden_field=forbidden_field):
                with self.assertRaisesRegex(InspectionError, "forbidden field"):
                    sanitize_controls(
                        [{"tag": "BUTTON", forbidden_field: "sensitive"}]
                    )

    def test_omits_password_hidden_and_non_mapping_controls(self) -> None:
        result = sanitize_controls(
            [
                {"tag": "INPUT", "type": "password", "id": "secret"},
                {"tag": "INPUT", "type": "hidden", "id": "state"},
                "not a control",
                {"tag": "BUTTON", "text": "Export"},
            ]
        )

        self.assertEqual(result, [{"tag": "BUTTON", "text": "Export"}])

    def test_rejects_non_list_payload_and_caps_control_count(self) -> None:
        with self.assertRaisesRegex(InspectionError, "must be a list"):
            sanitize_controls({"tag": "BUTTON"})

        result = sanitize_controls([{"tag": "BUTTON"}] * 5, max_controls=2)

        self.assertEqual(len(result), 2)

    def test_rejects_invalid_safety_limits(self) -> None:
        with self.assertRaises(InspectionError):
            sanitize_controls([], max_controls=0)
        with self.assertRaises(InspectionError):
            sanitize_controls([], max_text_length=0)

    def test_dom_script_does_not_read_sensitive_browser_properties(self) -> None:
        forbidden_fragments = (
            ".value",
            ".href",
            ".src",
            "document.cookie",
            "localStorage",
            "sessionStorage",
        )

        for fragment in forbidden_fragments:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, CONTROL_INSPECTION_SCRIPT)


if __name__ == "__main__":
    unittest.main()
