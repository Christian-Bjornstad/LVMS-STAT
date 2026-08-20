from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lvms_stat.workflow import (
    ControlIdentity,
    ParameterRole,
    StepKind,
    WorkflowDraft,
    WorkflowStep,
)
from lvms_stat.workflow_store import StoreError, WorkflowStore


class WorkflowStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "workflows"
        self.draft = WorkflowDraft(
            "Weekly report",
            "Safe note",
            (
                WorkflowStep(
                    1,
                    StepKind.FIELD_EDITED,
                    ControlIdentity("INPUT", element_id="from-date", label="From date"),
                    ParameterRole.FROM_DATE,
                ),
            ),
            True,
        )

    def test_round_trips_strict_safe_schema(self) -> None:
        store = WorkflowStore(self.root.resolve())
        saved = store.save(self.draft)
        payload = saved.read_text(encoding="utf-8")
        self.assertNotRegex(
            payload.lower(),
            r'"(value|url|path|filename|cookie|token|authorization)"\s*:',
        )
        self.assertNotIn("Weekly report", saved.name)
        self.assertEqual(store.load(saved), self.draft)

    def test_rejects_unknown_keys_and_schema_versions(self) -> None:
        self.root.mkdir()
        path = self.root / "unsafe.json"
        for payload in (
            {"schema_version": 2},
            {"schema_version": 1, "name": "X", "notes": "", "steps": [],
             "download_detected": False, "value": "forbidden"},
        ):
            with self.subTest(payload=payload):
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(StoreError):
                    WorkflowStore(self.root.resolve()).load(path)

    def test_requires_absolute_root_and_contained_load_path(self) -> None:
        with self.assertRaises(StoreError):
            WorkflowStore(Path("relative"))
        self.root.mkdir()
        outside = Path(self.temp.name) / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        with self.assertRaises(StoreError):
            WorkflowStore(self.root.resolve()).load(outside)


if __name__ == "__main__":
    unittest.main()
