from __future__ import annotations

import unittest

from lvms_stat.batch_controls import (
    BatchControlError,
    DocumentControlIdentity,
    validate_document_control,
)
from lvms_stat.control_identity import ControlIdentity


def control(tag: str, element_id: str) -> ControlIdentity:
    return ControlIdentity(tag, element_id=element_id)


class BatchControlTests(unittest.TestCase):
    def test_accepts_top_and_bounded_named_frame(self) -> None:
        top = validate_document_control(
            DocumentControlIdentity("top", control("SELECT", "jobtypeselector"))
        )
        framed = validate_document_control(
            DocumentControlIdentity(
                "_nav_frame1", control("BUTTON", "export")
            )
        )

        self.assertEqual(top.frame, "top")
        self.assertEqual(framed.frame, "_nav_frame1")

    def test_rejects_unsafe_frame_or_wrapped_control(self) -> None:
        invalid = ("", "https://frame.invalid", "../frame", "a" * 121)
        for frame in invalid:
            with self.subTest(frame=frame):
                with self.assertRaises(BatchControlError):
                    validate_document_control(
                        DocumentControlIdentity(
                            frame, control("BUTTON", "export")
                        )
                    )
        with self.assertRaises(BatchControlError):
            validate_document_control(
                DocumentControlIdentity("top", object())  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
