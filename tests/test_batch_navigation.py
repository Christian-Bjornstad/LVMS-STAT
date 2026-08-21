from __future__ import annotations

import unittest

from lvms_stat.batch_controls import DocumentControlIdentity
from lvms_stat.batch_navigation import (
    BatchNavigationError,
    DefinedReportsNavigator,
    discover_defined_reports_page,
    discover_navigation_anchor,
)


EXPECTED_ORIGIN = "https://lvms.example.invalid"
OTHER_ORIGIN = "https://other.example.invalid"


def raw_control(
    tag: str,
    element_id: str,
    *,
    name: str = "",
    control_type: str = "",
    label: str = "",
) -> dict[str, object]:
    return {
        "tag": tag,
        "type": control_type,
        "id": element_id,
        "name": name,
        "role": "",
        "label": label,
        "locator": [f"{tag.lower()}#{element_id}"],
    }


def raw_document(
    frame: str, control: dict[str, object]
) -> dict[str, object]:
    return {"frame": frame, "control": control}


def page_contract_payload() -> dict[str, object]:
    return {
        "job_type": raw_document(
            "top",
            raw_control(
                "SELECT",
                "jobtypeselector",
                name="jobtypeselector",
            ),
        ),
        "clear": raw_document(
            "_nav_frame1",
            raw_control("BUTTON", "clear", name="menu", control_type="button"),
        ),
        "export": raw_document(
            "_nav_frame1",
            raw_control("BUTTON", "export", name="menu", control_type="button"),
        ),
    }


class FakeSafePage:
    def __init__(self, payload: object, origin: str = EXPECTED_ORIGIN) -> None:
        self.payload = payload
        self.origin = origin
        self.expressions: list[str] = []

    def current_origin(self) -> str:
        return self.origin

    def evaluate_safe(self, expression: str, *, timeout_seconds: float = 2) -> object:
        del timeout_seconds
        self.expressions.append(expression)
        return self.payload


class NavigationState:
    def __init__(self, route: tuple[str, ...] = (), *, destination: bool = False) -> None:
        self.route = route
        self.position = 0
        self.destination = destination
        self.origin = EXPECTED_ORIGIN
        self.activations: list[str] = []
        self.page = self
        self.actions = self

    def current_origin(self) -> str:
        return self.origin

    def evaluate_safe(self, expression: str, *, timeout_seconds: float = 2) -> object:
        del timeout_seconds
        if "LVMS_DEFINED_REPORTS_PAGE" in expression:
            return page_contract_payload() if self.destination else None
        if "LVMS_NAVIGATION_ANCHOR" in expression:
            if self.position >= len(self.route):
                return None
            next_step = self.route[self.position]
            if next_step == "section" and "Eksterne rapporter" in expression:
                return raw_document(
                    "top", raw_control("A", "section", label="external reports")
                )
            if next_step == "defined_reports" and "Definerte rapporter" in expression:
                return raw_document(
                    "top", raw_control("A", "defined_reports", label="defined reports")
                )
            return None
        raise AssertionError("unexpected safe expression")

    def activate(self, identity: DocumentControlIdentity) -> None:
        step = identity.control.element_id
        self.activations.append(step)
        if self.position >= len(self.route) or step != self.route[self.position]:
            raise AssertionError("unexpected navigation action")
        self.position += 1
        if self.position == len(self.route):
            self.destination = True


class TickingClock:
    def __init__(self) -> None:
        self.value = -1.0

    def __call__(self) -> float:
        self.value += 1.0
        return self.value


class BatchNavigationTests(unittest.TestCase):
    def test_page_requires_all_three_controls_in_exact_documents(self) -> None:
        page = FakeSafePage(page_contract_payload())

        contract = discover_defined_reports_page(page, EXPECTED_ORIGIN)

        self.assertIsNotNone(contract)
        assert contract is not None
        self.assertEqual(contract.job_type.frame, "top")
        self.assertEqual(contract.job_type.control.element_id, "jobtypeselector")
        self.assertEqual(contract.clear.frame, "_nav_frame1")
        self.assertEqual(contract.export.control.element_id, "export")
        expression = page.expressions[0]
        self.assertNotIn(".src", expression)
        self.assertNotIn(".value", expression)
        self.assertIn("visible(frame)", expression)

    def test_page_rejects_absent_or_wrong_origin_contract(self) -> None:
        self.assertIsNone(
            discover_defined_reports_page(FakeSafePage(None), EXPECTED_ORIGIN)
        )
        with self.assertRaises(BatchNavigationError):
            discover_defined_reports_page(
                FakeSafePage(page_contract_payload(), OTHER_ORIGIN), EXPECTED_ORIGIN
            )

    def test_page_rejects_malformed_or_wrong_structural_contract(self) -> None:
        malformed = page_contract_payload()
        malformed["export"] = None
        wrong = page_contract_payload()
        wrong["clear"] = raw_document(
            "top", raw_control("BUTTON", "clear", name="menu", control_type="button")
        )
        for payload in (malformed, wrong):
            with self.subTest(payload=payload):
                with self.assertRaises(BatchNavigationError):
                    discover_defined_reports_page(
                        FakeSafePage(payload), EXPECTED_ORIGIN
                    )

    def test_navigation_anchor_is_allowlisted_exact_and_top_document_only(self) -> None:
        payload = raw_document(
            "top", raw_control("A", "defined_reports", label="defined reports")
        )
        page = FakeSafePage(payload)

        anchor = discover_navigation_anchor(
            page, EXPECTED_ORIGIN, "Definerte rapporter"
        )

        self.assertIsNotNone(anchor)
        assert anchor is not None
        self.assertEqual(anchor.frame, "top")
        expression = page.expressions[0]
        self.assertIn("matches.length === 1", expression)
        with self.assertRaises(BatchNavigationError):
            discover_navigation_anchor(page, EXPECTED_ORIGIN, "Arbitrary label")

    def test_navigator_accepts_page_already_at_destination(self) -> None:
        state = NavigationState(destination=True)
        navigator = DefinedReportsNavigator(
            EXPECTED_ORIGIN, clock=lambda: 0.0, sleep=lambda seconds: None
        )

        result = navigator.reach(state.page, state.actions)

        self.assertEqual(result.export.control.element_id, "export")
        self.assertEqual(state.activations, [])

    def test_navigator_uses_direct_or_section_then_defined_reports_route(self) -> None:
        for route in (("defined_reports",), ("section", "defined_reports")):
            with self.subTest(route=route):
                state = NavigationState(route)
                navigator = DefinedReportsNavigator(
                    EXPECTED_ORIGIN,
                    clock=lambda: 0.0,
                    sleep=lambda seconds: None,
                )

                navigator.reach(state.page, state.actions)

                self.assertEqual(state.activations, list(route))

    def test_navigator_stops_after_origin_change_or_deadline(self) -> None:
        state = NavigationState(("defined_reports",))

        class OriginChangingActions:
            def activate(self, identity: DocumentControlIdentity) -> None:
                state.activate(identity)
                state.origin = OTHER_ORIGIN

        navigator = DefinedReportsNavigator(
            EXPECTED_ORIGIN, clock=lambda: 0.0, sleep=lambda seconds: None
        )
        with self.assertRaises(BatchNavigationError):
            navigator.reach(state.page, OriginChangingActions())

        unavailable = NavigationState()
        timed = DefinedReportsNavigator(
            EXPECTED_ORIGIN,
            timeout_seconds=2,
            clock=TickingClock(),
            sleep=lambda seconds: None,
        )
        with self.assertRaises(BatchNavigationError):
            timed.reach(unavailable.page, unavailable.actions)

    def test_navigator_only_polls_after_defined_reports_activation(self) -> None:
        class DelayedDestination:
            def __init__(self) -> None:
                self.activations: list[str] = []
                self.destination_checks = 0

            def current_origin(self) -> str:
                return EXPECTED_ORIGIN

            def evaluate_safe(
                self, expression: str, *, timeout_seconds: float = 2
            ) -> object:
                del timeout_seconds
                if "LVMS_DEFINED_REPORTS_PAGE" in expression:
                    self.destination_checks += 1
                    return (
                        page_contract_payload()
                        if self.destination_checks >= 3
                        else None
                    )
                if "Definerte rapporter" in expression:
                    return raw_document(
                        "top", raw_control("A", "defined_reports")
                    )
                if "Eksterne rapporter" in expression:
                    return raw_document("top", raw_control("A", "section"))
                raise AssertionError("unexpected expression")

            def activate(self, identity: DocumentControlIdentity) -> None:
                self.activations.append(identity.control.element_id)

        state = DelayedDestination()
        navigator = DefinedReportsNavigator(
            EXPECTED_ORIGIN, clock=lambda: 0.0, sleep=lambda seconds: None
        )

        navigator.reach(state, state)

        self.assertEqual(state.activations, ["defined_reports"])


if __name__ == "__main__":
    unittest.main()
