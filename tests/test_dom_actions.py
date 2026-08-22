from __future__ import annotations

import unittest

from lvms_stat.batch_controls import DocumentControlIdentity
from lvms_stat.control_identity import ControlIdentity
from lvms_stat.dom_actions import DocumentDomActions


EXPECTED_ORIGIN = "https://lvms.example.invalid"


class HoverPage:
    def __init__(self) -> None:
        self.hovered: list[str] = []

    def current_origin(self) -> str:
        return EXPECTED_ORIGIN

    def resolve_document_control(self, control: DocumentControlIdentity) -> str | None:
        del control
        return "a" * 32

    def hover_control(self, token: str) -> None:
        self.hovered.append(token)


class DocumentDomActionsTests(unittest.TestCase):
    def test_hover_resolves_identity_before_moving_pointer(self) -> None:
        page = HoverPage()
        actions = DocumentDomActions(page, EXPECTED_ORIGIN)  # type: ignore[arg-type]

        actions.hover(DocumentControlIdentity("top", ControlIdentity("A")))

        self.assertEqual(page.hovered, ["a" * 32])


if __name__ == "__main__":
    unittest.main()
