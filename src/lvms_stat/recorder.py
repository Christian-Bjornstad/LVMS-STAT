from __future__ import annotations

import json
import secrets
from collections.abc import Callable, Mapping
from typing import Any

from lvms_stat.cdp import CdpError, UnexpectedOriginError
from lvms_stat.recorder_events import (
    RECORDER_DRAIN_SCRIPT_TEMPLATE,
    RECORDER_INSTALL_SCRIPT_TEMPLATE,
    RecorderEventError,
    sanitize_event_batch,
)
from lvms_stat.workflow import WorkflowStep


class RecorderUnavailable(RuntimeError):
    """The safe browser recorder could not continue."""


class RecorderSession:
    def __init__(
        self,
        page: Any,
        expected_origin: str,
        *,
        nonce_factory: Callable[[], str] = lambda: secrets.token_urlsafe(24),
    ) -> None:
        self._page = page
        self._expected_origin = expected_origin
        self._nonce = nonce_factory()
        self._marker = ""
        self._next_step_id = 1

    def _verify_origin(self) -> None:
        if self._page.current_origin() != self._expected_origin:
            raise UnexpectedOriginError("Edge reached an unexpected origin")

    def _script(self, template: str) -> str:
        return template.replace("__NONCE_JSON__", json.dumps(self._nonce))

    def install(self) -> None:
        self._verify_origin()
        try:
            marker = self._page.evaluate_safe(
                self._script(RECORDER_INSTALL_SCRIPT_TEMPLATE), timeout_seconds=5
            )
        except CdpError as exc:
            raise RecorderUnavailable("safe recorder listener is unavailable") from exc
        if not isinstance(marker, str) or not marker or len(marker) > 120:
            raise RecorderUnavailable("safe recorder listener is unavailable")
        self._marker = marker

    def poll(self) -> tuple[WorkflowStep, ...]:
        self._verify_origin()
        try:
            raw = self._page.evaluate_safe(
                self._script(RECORDER_DRAIN_SCRIPT_TEMPLATE), timeout_seconds=2
            )
            if not isinstance(raw, Mapping) or set(raw) != {"marker", "events"}:
                self.install()
                return ()
            if raw["marker"] != self._marker:
                self.install()
                return ()
            steps = sanitize_event_batch(
                raw["events"],
                start_step_id=self._next_step_id,
                expected_nonce=self._nonce,
            )
        except UnexpectedOriginError:
            raise
        except (CdpError, RecorderEventError) as exc:
            raise RecorderUnavailable("safe recorder listener is unavailable") from exc
        self._next_step_id += len(steps)
        return steps
