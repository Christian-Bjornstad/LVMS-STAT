from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lvms_stat.report_contract import (
    ReportContractError,
    discover_report_contract,
    load_contract,
    sanitize_report_contract,
    save_contract,
)


def identity(tag: str, element_id: str) -> dict[str, object]:
    return {
        "tag": tag,
        "type": "",
        "id": element_id,
        "name": "",
        "role": "",
        "label": "",
        "locator": [f"{tag.lower()}#{element_id}"],
    }


def payload() -> dict[str, object]:
    return {
        "report_type": identity("SELECT", "report-type"),
        "category": identity("SELECT", "category"),
        "report_id": identity("SELECT", "report-id"),
        "analysis_codes": identity("INPUT", "analyses"),
        "created_from": identity("INPUT", "created-from"),
        "created_to": identity("INPUT", "created-to"),
        "export": identity("BUTTON", "export"),
    }


class FakePage:
    def __init__(self, raw: object, origin: str = "https://lvms.example.invalid") -> None:
        self.raw = raw
        self.origin = origin
        self.expressions: list[str] = []

    def current_origin(self) -> str:
        return self.origin

    def evaluate_safe(self, expression: str, *, timeout_seconds: float = 2) -> object:
        del timeout_seconds
        self.expressions.append(expression)
        return self.raw


class ReportContractTests(unittest.TestCase):
    def test_requires_one_safe_control_for_every_role(self) -> None:
        contract = sanitize_report_contract(payload())

        self.assertEqual(contract.report_type.element_id, "report-type")
        self.assertEqual(contract.export.tag, "BUTTON")

    def test_rejects_values_unknown_roles_and_duplicate_controls(self) -> None:
        with_value = payload()
        with_value["analysis_codes"] = {
            **with_value["analysis_codes"],  # type: ignore[arg-type]
            "value": "SECRET",
        }
        unknown = {**payload(), "other": identity("INPUT", "other")}
        duplicate = payload()
        duplicate["category"] = identity("SELECT", "report-type")
        for raw in (with_value, unknown, duplicate):
            with self.subTest(raw=raw):
                with self.assertRaises(ReportContractError):
                    sanitize_report_contract(raw)

    def test_discovers_only_on_expected_origin(self) -> None:
        page = FakePage(payload())
        contract = discover_report_contract(page, "https://lvms.example.invalid")
        self.assertEqual(contract.report_id.element_id, "report-id")
        self.assertEqual(len(page.expressions), 1)

        with self.assertRaises(ReportContractError):
            discover_report_contract(
                FakePage(payload(), "https://unexpected.invalid"),
                "https://lvms.example.invalid",
            )

    def test_stores_opaque_contract_without_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            path = save_contract(sanitize_report_contract(payload()), root)
            text = path.read_text(encoding="utf-8")

            self.assertEqual(path.parent, root)
            self.assertEqual(path.suffix, ".json")
            self.assertNotIn("value", text.casefold())
            self.assertNotIn("REPORT-A", text)
            self.assertEqual(load_contract(path, root).export.element_id, "export")

    def test_stored_contract_rejects_unknown_control_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            path = save_contract(sanitize_report_contract(payload()), root)
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["roles"]["export"]["unexpected"] = "unsafe"
            path.write_text(json.dumps(raw), encoding="utf-8")

            with self.assertRaisesRegex(ReportContractError, "control is invalid"):
                load_contract(path, root)


if __name__ == "__main__":
    unittest.main()
