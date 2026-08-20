from __future__ import annotations

import unittest

from lvms_stat.workflow import (
    ControlIdentity,
    ParameterRole,
    RecorderState,
    StepKind,
    WorkflowDraft,
    WorkflowError,
    WorkflowStep,
    assign_parameter_role,
    transition,
    validate_workflow,
)


class WorkflowTests(unittest.TestCase):
    def test_allows_only_declared_state_transitions(self) -> None:
        self.assertEqual(transition(RecorderState.READY, "start"), RecorderState.STARTING)
        self.assertEqual(
            transition(RecorderState.STARTING, "connected"), RecorderState.RECORDING
        )
        self.assertEqual(
            transition(RecorderState.RECORDING, "stop"), RecorderState.STOPPED
        )
        with self.assertRaises(WorkflowError):
            transition(RecorderState.READY, "download_detected")

    def test_assigns_role_only_to_edited_field(self) -> None:
        field = WorkflowStep(1, StepKind.FIELD_EDITED, ControlIdentity("INPUT"))
        draft = WorkflowDraft("Weekly report", "Safe note", (field,))

        updated = assign_parameter_role(draft, 1, ParameterRole.FROM_DATE)

        self.assertEqual(updated.steps[0].parameter_role, ParameterRole.FROM_DATE)
        self.assertNotIn("value", updated.steps[0].__dataclass_fields__)
        click = WorkflowDraft(
            "Weekly report", "", (WorkflowStep(1, StepKind.ACTIVATE, ControlIdentity("BUTTON")),)
        )
        with self.assertRaises(WorkflowError):
            assign_parameter_role(click, 1, ParameterRole.TO_DATE)

    def test_validates_bounded_name_notes_and_sequential_steps(self) -> None:
        validate_workflow(WorkflowDraft("A" * 80, "B" * 500))
        for draft in (
            WorkflowDraft("", ""),
            WorkflowDraft("A" * 81, ""),
            WorkflowDraft("Valid", "B" * 501),
            WorkflowDraft(
                "Valid", "", (WorkflowStep(2, StepKind.ACTIVATE, ControlIdentity("BUTTON")),)
            ),
        ):
            with self.subTest(draft=draft):
                with self.assertRaises(WorkflowError):
                    validate_workflow(draft)

    def test_rejects_unbounded_or_malformed_control_identity(self) -> None:
        invalid_controls = (
            ControlIdentity(""),
            ControlIdentity("BUTTON", label="x" * 121),
            ControlIdentity("BUTTON", locator=("x",) * 13),
            ControlIdentity("BUTTON", locator=("x" * 121,)),
            ControlIdentity(1),  # type: ignore[arg-type]
        )
        for control in invalid_controls:
            with self.subTest(control=control):
                draft = WorkflowDraft(
                    "Valid", "", (WorkflowStep(1, StepKind.ACTIVATE, control),)
                )
                with self.assertRaises(WorkflowError):
                    validate_workflow(draft)


if __name__ == "__main__":
    unittest.main()
