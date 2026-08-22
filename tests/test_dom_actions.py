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


class ChoicePage:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def current_origin(self) -> str:
        return EXPECTED_ORIGIN

    def resolve_document_control(self, control: DocumentControlIdentity) -> str | None:
        del control
        return "a" * 32

    def choose_native_option(self, token: str, text: str) -> bool:
        del token, text
        return False

    def focus_control(self, token: str) -> None:
        self.events.append(("focus", token))

    def activate_control(self, token: str) -> None:
        self.events.append(("activate", token))

    def replace_focused_text(self, text: str) -> None:
        self.events.append(("replace", text))

    def press_key(self, key: str) -> None:
        self.events.append(("key", key))


class DocumentDomActionsTests(unittest.TestCase):
    def test_hover_resolves_identity_before_moving_pointer(self) -> None:
        page = HoverPage()
        actions = DocumentDomActions(page, EXPECTED_ORIGIN)  # type: ignore[arg-type]

        actions.hover(DocumentControlIdentity("top", ControlIdentity("A")))

        self.assertEqual(page.hovered, ["a" * 32])

    def test_custom_choice_stays_in_field_until_next_control_is_focused(self) -> None:
        page = ChoicePage()
        actions = DocumentDomActions(page, EXPECTED_ORIGIN)  # type: ignore[arg-type]

        actions.choose_text(
            DocumentControlIdentity("top", ControlIdentity("INPUT")),
            "REPORT-A",
        )

        self.assertEqual(
            page.events,
            [
                ("focus", "a" * 32),
                ("replace", "REPORT-A"),
            ],
        )

    def test_text_field_is_activated_before_replacing_grid_value(self) -> None:
        page = ChoicePage()
        actions = DocumentDomActions(page, EXPECTED_ORIGIN)  # type: ignore[arg-type]

        actions.replace_text(
            DocumentControlIdentity("top", ControlIdentity("INPUT")),
            "VALUE-A",
        )

        self.assertEqual(
            page.events,
            [
                ("activate", "a" * 32),
                ("focus", "a" * 32),
                ("replace", "VALUE-A"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
