from __future__ import annotations

import unittest

from lvms_stat.cdp import UnexpectedOriginError
from lvms_stat.recorder import RecorderSession, RecorderUnavailable


class FakePage:
    def __init__(self, evaluations: list[object], origin: str = "https://lvms.example.invalid") -> None:
        self.origin = origin
        self.evaluations = list(evaluations)
        self.expressions: list[str] = []

    def current_origin(self) -> str:
        return self.origin

    def evaluate_safe(self, expression: str, *, timeout_seconds: float = 2) -> object:
        del timeout_seconds
        self.expressions.append(expression)
        value = self.evaluations.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def candidate(nonce: str) -> dict[str, object]:
    return {
        "nonce": nonce,
        "kind": "activate",
        "control": {
            "tag": "BUTTON", "type": "button", "id": "export", "name": "",
            "role": "button", "label": "Export", "locator": ["button#export"],
        },
    }


class RecorderTests(unittest.TestCase):
    def test_installs_and_polls_sequential_safe_steps(self) -> None:
        page = FakePage(["marker-1", {"marker": "marker-1", "events": [candidate("safe-nonce")]}])
        session = RecorderSession(
            page, "https://lvms.example.invalid", nonce_factory=lambda: "safe-nonce"
        )
        session.install()

        steps = session.poll()

        self.assertEqual(steps[0].step_id, 1)
        self.assertNotIn("safe-nonce", repr(session))

    def test_rechecks_origin_before_drain(self) -> None:
        page = FakePage(["marker-1"])
        session = RecorderSession(page, "https://lvms.example.invalid", nonce_factory=lambda: "n")
        session.install()
        page.origin = "https://unexpected.invalid"
        with self.assertRaises(UnexpectedOriginError):
            session.poll()
        self.assertEqual(len(page.expressions), 1)

    def test_fails_closed_on_wrong_nonce_or_invalid_payload(self) -> None:
        page = FakePage(["marker-1", {"marker": "marker-1", "events": [candidate("late")] }])
        session = RecorderSession(page, "https://lvms.example.invalid", nonce_factory=lambda: "current")
        session.install()
        with self.assertRaises(RecorderUnavailable) as caught:
            session.poll()
        self.assertNotIn("late", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
