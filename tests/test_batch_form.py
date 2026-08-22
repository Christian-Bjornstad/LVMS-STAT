from __future__ import annotations

import unittest

from lvms_stat.batch_controls import DocumentControlIdentity
from lvms_stat.batch_form import (
    BatchFormError,
    BatchReportForm,
    discover_report_role,
)
from lvms_stat.batch_navigation import DefinedReportsPage
from lvms_stat.report_job import ReportJob, validate_report_job
from lvms_stat.control_identity import ControlIdentity


EXPECTED_ORIGIN = "https://lvms.example.invalid"
OTHER_ORIGIN = "https://other.example.invalid"


def raw_control(
    tag: str,
    element_id: str,
    *,
    label: str,
    control_type: str = "",
    role: str = "",
) -> dict[str, object]:
    return {
        "frame": "_nav_frame1",
        "control": {
            "tag": tag,
            "type": control_type,
            "id": element_id,
            "name": element_id,
            "role": role,
            "label": label,
            "locator": [f"{tag.lower()}#{element_id}"],
        },
    }


ROLE_PAYLOADS = {
    "category": raw_control("SELECT", "category", label="kategori"),
    "report_id": raw_control("SELECT", "report-id", label="rapport id"),
    "analysis_codes": raw_control("TEXTAREA", "analyses", label="angi analyse(r)"),
    "created_from": raw_control(
        "INPUT", "created-from", label="analyse opprettet fom:", control_type="text"
    ),
    "created_to": raw_control(
        "INPUT", "created-to", label="analyse opprettet tom:", control_type="text"
    ),
}


def identity(
    frame: str, tag: str, element_id: str, **values: str
) -> DocumentControlIdentity:
    return DocumentControlIdentity(
        frame,
        ControlIdentity(tag, element_id=element_id, **values),
    )


def defined_reports_page() -> DefinedReportsPage:
    return DefinedReportsPage(
        job_type=identity(
            "top",
            "SELECT",
            "jobtypeselector",
            name="jobtypeselector",
        ),
        clear=identity(
            "_nav_frame1",
            "BUTTON",
            "clear",
            name="menu",
            control_type="button",
        ),
        export=identity(
            "_nav_frame1",
            "BUTTON",
            "export",
            name="menu",
            control_type="button",
        ),
    )


def job() -> ReportJob:
    return validate_report_job(
        {
            "job_key": "ordered",
            "report_type": "TYPE_A",
            "category": "CATEGORY_A",
            "report_id": "REPORT-A",
            "analysis_codes": ["ANALYSIS-A", "ANALYSIS-B"],
            "created_from": "01.08.2026",
            "created_to": "07.08.2026",
            "output_stem": "ordered",
        }
    )


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


class FormState:
    def __init__(self, *, missing_role: str | None = None) -> None:
        self.missing_role = missing_role
        self.calls: list[tuple[str, str, str, str]] = []
        self.page = self
        self.actions = self

    def current_origin(self) -> str:
        return EXPECTED_ORIGIN

    def evaluate_safe(self, expression: str, *, timeout_seconds: float = 2) -> object:
        del timeout_seconds
        for role, payload in ROLE_PAYLOADS.items():
            if f'const requestedRole = "{role}"' in expression:
                return None if role == self.missing_role else payload
        raise AssertionError("requested role was not encoded")

    def choose_text(self, control: DocumentControlIdentity, text: str) -> None:
        self.calls.append(("choose", control.frame, control.control.element_id, text))

    def replace_text(self, control: DocumentControlIdentity, text: str) -> None:
        self.calls.append(("replace", control.frame, control.control.element_id, text))


class TickingClock:
    def __init__(self) -> None:
        self.value = -1.0

    def __call__(self) -> float:
        self.value += 1.0
        return self.value


class ClearingPage:
    def __init__(self, *, clears_after_category_checks: int | None) -> None:
        self.clears_after_category_checks = clears_after_category_checks
        self.category_checks = 0

    def current_origin(self) -> str:
        return EXPECTED_ORIGIN

    def evaluate_safe(self, expression: str, *, timeout_seconds: float = 2) -> object:
        del timeout_seconds
        if 'const requestedRole = "category"' in expression:
            self.category_checks += 1
            if (
                self.clears_after_category_checks is None
                or self.category_checks <= self.clears_after_category_checks
            ):
                return ROLE_PAYLOADS["category"]
        return None


class BatchFormTests(unittest.TestCase):
    def test_discovers_each_supported_role_across_named_documents(self) -> None:
        expected_ids = {
            "category": "category",
            "report_id": "report-id",
            "analysis_codes": "analyses",
            "created_from": "created-from",
            "created_to": "created-to",
        }
        for role, expected_id in expected_ids.items():
            with self.subTest(role=role):
                page = FakeSafePage(ROLE_PAYLOADS[role])

                result = discover_report_role(page, EXPECTED_ORIGIN, role)

                self.assertIsNotNone(result)
                assert result is not None
                self.assertEqual(result.control.element_id, expected_id)
                script = page.expressions[0]
                for forbidden in (
                    ".value",
                    ".src",
                    ".href",
                    "document.cookie",
                    "localStorage",
                    "sessionStorage",
                ):
                    self.assertNotIn(forbidden, script)
                self.assertNotIn("!el.readOnly", script)
                self.assertIn("if (!visible(frame)) continue;", script)
                self.assertIn("ambiguous: true", script)
                self.assertIn("[role='grid']", script)
                self.assertIn("[id*='patient' i]", script)

    def test_role_discovery_rejects_unknown_absent_or_wrong_origin(self) -> None:
        with self.assertRaises(BatchFormError):
            discover_report_role(FakeSafePage(None), EXPECTED_ORIGIN, "unknown")
        self.assertIsNone(
            discover_report_role(FakeSafePage(None), EXPECTED_ORIGIN, "category")
        )
        with self.assertRaises(BatchFormError):
            discover_report_role(
                FakeSafePage(ROLE_PAYLOADS["category"], OTHER_ORIGIN),
                EXPECTED_ORIGIN,
                "category",
            )

    def test_role_discovery_rejects_incompatible_or_unsafe_controls(self) -> None:
        invalid = (
            raw_control("BUTTON", "category", label="kategori"),
            raw_control("INPUT", "category", label="kategori", control_type="hidden"),
            raw_control("INPUT", "category", label="kategori", role="gridcell"),
            {**ROLE_PAYLOADS["category"], "frame": ""},
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(BatchFormError):
                    discover_report_role(
                        FakeSafePage(payload), EXPECTED_ORIGIN, "category"
                    )

    def test_populate_advances_in_strict_stage_order(self) -> None:
        state = FormState()
        form = BatchReportForm(
            state.page,
            state.actions,
            EXPECTED_ORIGIN,
            clock=lambda: 0.0,
            sleep=lambda seconds: None,
        )

        form.populate(defined_reports_page(), job())

        self.assertEqual(
            state.calls,
            [
                ("choose", "top", "jobtypeselector", "TYPE_A"),
                ("choose", "_nav_frame1", "category", "CATEGORY_A"),
                ("choose", "_nav_frame1", "report-id", "REPORT-A"),
                ("replace", "_nav_frame1", "analyses", "ANALYSIS-A,ANALYSIS-B"),
                ("replace", "_nav_frame1", "created-from", "01.08.2026"),
                ("replace", "_nav_frame1", "created-to", "07.08.2026"),
            ],
        )

    def test_missing_stage_stops_before_later_actions(self) -> None:
        state = FormState(missing_role="report_id")
        form = BatchReportForm(
            state.page,
            state.actions,
            EXPECTED_ORIGIN,
            timeout_seconds=2,
            clock=TickingClock(),
            sleep=lambda seconds: None,
        )

        with self.assertRaises(BatchFormError):
            form.populate(defined_reports_page(), job())

        self.assertEqual(
            state.calls,
            [
                ("choose", "top", "jobtypeselector", "TYPE_A"),
                ("choose", "_nav_frame1", "category", "CATEGORY_A"),
            ],
        )

    def test_wait_until_clear_requires_every_dynamic_role_to_be_absent(self) -> None:
        page = ClearingPage(clears_after_category_checks=1)
        form = BatchReportForm(
            page,
            FormState().actions,
            EXPECTED_ORIGIN,
            clock=lambda: 0.0,
            sleep=lambda seconds: None,
        )

        form.wait_until_clear()

        self.assertEqual(page.category_checks, 2)

    def test_wait_until_clear_times_out_while_a_dynamic_role_remains(self) -> None:
        page = ClearingPage(clears_after_category_checks=None)
        form = BatchReportForm(
            page,
            FormState().actions,
            EXPECTED_ORIGIN,
            timeout_seconds=2,
            clock=TickingClock(),
            sleep=lambda seconds: None,
        )

        with self.assertRaises(BatchFormError):
            form.wait_until_clear()


if __name__ == "__main__":
    unittest.main()
