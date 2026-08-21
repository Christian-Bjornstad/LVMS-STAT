from __future__ import annotations

from typing import Protocol

from lvms_stat.workflow import ControlIdentity


class DomActionError(RuntimeError):
    """A requested report-page action could not be performed safely."""


class ActionPage(Protocol):
    def current_origin(self) -> str: ...

    def resolve_control(self, control: ControlIdentity) -> str | None: ...

    def focus_control(self, token: str) -> None: ...

    def activate_control(self, token: str) -> None: ...

    def replace_focused_text(self, text: str) -> None: ...

    def choose_native_option(self, token: str, text: str) -> bool: ...

    def press_key(self, key: str) -> None: ...


class DomActions:
    def __init__(self, page: ActionPage, expected_origin: str) -> None:
        self._page = page
        self._expected_origin = expected_origin

    def _resolve(self, control: ControlIdentity) -> str:
        if self._page.current_origin() != self._expected_origin:
            raise DomActionError("Edge reached an unexpected origin")
        token = self._page.resolve_control(control)
        if token is None:
            raise DomActionError("report control is not uniquely available")
        return token

    def activate(self, control: ControlIdentity) -> None:
        self._page.activate_control(self._resolve(control))

    def replace_text(self, control: ControlIdentity, text: str) -> None:
        token = self._resolve(control)
        self._page.focus_control(token)
        self._page.replace_focused_text(text)

    def choose_text(self, control: ControlIdentity, text: str) -> None:
        token = self._resolve(control)
        if self._page.choose_native_option(token, text):
            return
        self._page.focus_control(token)
        self._page.replace_focused_text(text)
        self._page.press_key("ENTER")
