from __future__ import annotations

import unittest

from lvms_stat.batch_controls import DocumentControlIdentity
from lvms_stat.dom_actions import DocumentDomActions, DomActionError, DomActions
from lvms_stat.workflow import ControlIdentity


class RecordingPage:
    def __init__(self, *, resolve_count: int = 1, native_select: bool = True) -> None:
        self.resolve_count = resolve_count
        self.native_select = native_select
        self.operations: list[tuple[object, ...]] = []

    def current_origin(self) -> str:
        self.operations.append(("origin", "https://lvms.example.invalid"))
        return "https://lvms.example.invalid"

    def resolve_control(self, control: ControlIdentity) -> str | None:
        self.operations.append(("resolve", control.element_id))
        return "safe-token" if self.resolve_count == 1 else None

    def focus_control(self, token: str) -> None:
        self.operations.append(("focus", token))

    def activate_control(self, token: str) -> None:
        self.operations.append(("activate", token))

    def replace_focused_text(self, text: str) -> None:
        self.operations.append(("replace", text))

    def choose_native_option(self, token: str, text: str) -> bool:
        self.operations.append(("choose_native", token, text))
        return self.native_select

    def press_key(self, key: str) -> None:
        self.operations.append(("key", key))


class RecordingDocumentPage(RecordingPage):
    def resolve_document_control(
        self, identity: DocumentControlIdentity
    ) -> str | None:
        self.operations.append(
            ("resolve_document", identity.frame, identity.control.element_id)
        )
        return "safe-token" if self.resolve_count == 1 else None


class DomActionTests(unittest.TestCase):
    def test_replace_text_resolves_one_control_and_never_reads_existing_value(self) -> None:
        page = RecordingPage()
        actions = DomActions(page, "https://lvms.example.invalid")

        actions.replace_text(
            ControlIdentity("INPUT", element_id="analyses"), "ANALYSIS-A"
        )

        self.assertEqual(
            page.operations,
            [
                ("origin", "https://lvms.example.invalid"),
                ("resolve", "analyses"),
                ("focus", "safe-token"),
                ("replace", "ANALYSIS-A"),
            ],
        )
        self.assertTrue(all("read_value" not in operation for operation in page.operations))

    def test_action_fails_when_control_is_not_unique(self) -> None:
        for count in (0, 2):
            with self.subTest(count=count):
                actions = DomActions(
                    RecordingPage(resolve_count=count),
                    "https://lvms.example.invalid",
                )
                with self.assertRaisesRegex(DomActionError, "not uniquely available"):
                    actions.activate(ControlIdentity("BUTTON", element_id="export"))

    def test_action_fails_closed_on_unexpected_origin(self) -> None:
        page = RecordingPage()
        actions = DomActions(page, "https://other.example.invalid")

        with self.assertRaisesRegex(DomActionError, "unexpected origin"):
            actions.activate(ControlIdentity("BUTTON", element_id="export"))

        self.assertEqual(page.operations, [("origin", "https://lvms.example.invalid")])

    def test_native_select_uses_exact_option_action(self) -> None:
        page = RecordingPage(native_select=True)
        actions = DomActions(page, "https://lvms.example.invalid")

        actions.choose_text(ControlIdentity("SELECT", element_id="report-type"), "PRODSTAT")

        self.assertEqual(page.operations[-1], ("choose_native", "safe-token", "PRODSTAT"))
        self.assertNotIn(("key", "ENTER"), page.operations)

    def test_custom_select_types_then_confirms_with_enter(self) -> None:
        page = RecordingPage(native_select=False)
        actions = DomActions(page, "https://lvms.example.invalid")

        actions.choose_text(ControlIdentity("INPUT", element_id="category"), "PATOLOGI")

        self.assertEqual(
            page.operations[-4:],
            [
                ("choose_native", "safe-token", "PATOLOGI"),
                ("focus", "safe-token"),
                ("replace", "PATOLOGI"),
                ("key", "ENTER"),
            ],
        )

    def test_document_actions_revalidate_origin_and_use_document_identity(self) -> None:
        page = RecordingDocumentPage()
        actions = DocumentDomActions(page, "https://lvms.example.invalid")

        actions.activate(
            DocumentControlIdentity(
                "_nav_frame1",
                ControlIdentity("BUTTON", element_id="export"),
            )
        )

        self.assertEqual(
            page.operations,
            [
                ("origin", "https://lvms.example.invalid"),
                ("resolve_document", "_nav_frame1", "export"),
                ("activate", "safe-token"),
            ],
        )

    def test_document_actions_fail_closed_when_control_is_not_unique(self) -> None:
        page = RecordingDocumentPage(resolve_count=0)
        actions = DocumentDomActions(page, "https://lvms.example.invalid")

        with self.assertRaisesRegex(DomActionError, "not uniquely available"):
            actions.replace_text(
                DocumentControlIdentity(
                    "_nav_frame1",
                    ControlIdentity("INPUT", element_id="analyses"),
                ),
                "ANALYSIS-A",
            )


if __name__ == "__main__":
    unittest.main()
