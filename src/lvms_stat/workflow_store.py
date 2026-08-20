from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from lvms_stat.workflow import (
    ControlIdentity,
    ParameterRole,
    StepKind,
    WorkflowDraft,
    WorkflowError,
    WorkflowStep,
    validate_workflow,
)


class StoreError(ValueError):
    """A workflow could not be stored without crossing its safe schema."""


_ROOT_KEYS = {"schema_version", "name", "notes", "steps", "download_detected"}
_STEP_KEYS = {"step_id", "kind", "control", "parameter_role"}
_CONTROL_KEYS = {"tag", "control_type", "element_id", "name", "role", "label", "locator"}


def _encode(draft: WorkflowDraft) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": draft.name,
        "notes": draft.notes,
        "steps": [
            {
                "step_id": step.step_id,
                "kind": step.kind.value,
                "control": {
                    "tag": step.control.tag,
                    "control_type": step.control.control_type,
                    "element_id": step.control.element_id,
                    "name": step.control.name,
                    "role": step.control.role,
                    "label": step.control.label,
                    "locator": list(step.control.locator),
                },
                "parameter_role": (
                    step.parameter_role.value if step.parameter_role is not None else None
                ),
            }
            for step in draft.steps
        ],
        "download_detected": draft.download_detected,
    }


def _exact_dict(value: object, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise StoreError("workflow file has an invalid schema")
    return value


def _decode(raw: object) -> WorkflowDraft:
    root = _exact_dict(raw, _ROOT_KEYS)
    if root["schema_version"] != 1 or not isinstance(root["steps"], list):
        raise StoreError("workflow file has an unsupported schema")
    steps: list[WorkflowStep] = []
    try:
        for item in root["steps"]:
            step = _exact_dict(item, _STEP_KEYS)
            control = _exact_dict(step["control"], _CONTROL_KEYS)
            locator = control["locator"]
            if not isinstance(locator, list) or not all(isinstance(x, str) for x in locator):
                raise StoreError("workflow file has an invalid locator")
            identity = ControlIdentity(
                tag=control["tag"],
                control_type=control["control_type"],
                element_id=control["element_id"],
                name=control["name"],
                role=control["role"],
                label=control["label"],
                locator=tuple(locator),
            )
            role = step["parameter_role"]
            steps.append(
                WorkflowStep(
                    step_id=step["step_id"],
                    kind=StepKind(step["kind"]),
                    control=identity,
                    parameter_role=ParameterRole(role) if role is not None else None,
                )
            )
        draft = WorkflowDraft(
            name=root["name"],
            notes=root["notes"],
            steps=tuple(steps),
            download_detected=root["download_detected"],
        )
        return validate_workflow(draft)
    except (KeyError, TypeError, ValueError, WorkflowError) as exc:
        raise StoreError("workflow file has invalid data") from exc


class WorkflowStore:
    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise StoreError("workflow directory must be absolute")
        self._root = root.resolve()

    def save(self, draft: WorkflowDraft) -> Path:
        try:
            safe = validate_workflow(draft)
        except WorkflowError as exc:
            raise StoreError("workflow is invalid") from exc
        self._root.mkdir(parents=True, exist_ok=True)
        destination = self._root / f"{uuid.uuid4().hex}.json"
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", delete=False, dir=self._root, suffix=".tmp"
            ) as stream:
                temporary = Path(stream.name)
                json.dump(_encode(safe), stream, ensure_ascii=False, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(destination)
            return destination
        except OSError as exc:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise StoreError("workflow could not be saved") from exc

    def load(self, path: Path) -> WorkflowDraft:
        resolved = path.resolve()
        if self._root not in resolved.parents:
            raise StoreError("workflow file is outside the storage directory")
        try:
            raw = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError("workflow file could not be read") from exc
        return _decode(raw)
