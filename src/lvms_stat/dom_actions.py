from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from lvms_stat.batch_controls import DocumentControlIdentity
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


ControlT = TypeVar("ControlT")


class _BaseDomActions(Generic[ControlT]):
    def __init__(self, page: ActionPage, expected_origin: str) -> None:
        self._page = page
        self._expected_origin = expected_origin

    def _require_expected_origin(self) -> None:
        if self._page.current_origin() != self._expected_origin:
            raise DomActionError("Edge reached an unexpected origin")

    def _resolve(self, control: ControlT) -> str:
        raise NotImplementedError

    def activate(self, control: ControlT) -> None:
        self._page.activate_control(self._resolve(control))

    def replace_text(self, control: ControlT, text: str) -> None:
        token = self._resolve(control)
        self._page.focus_control(token)
        self._page.replace_focused_text(text)

    def choose_text(self, control: ControlT, text: str) -> None:
        token = self._resolve(control)
        if self._page.choose_native_option(token, text):
            return
        self._page.focus_control(token)
        self._page.replace_focused_text(text)
        self._page.press_key("ENTER")


class DomActions(_BaseDomActions[ControlIdentity]):
    def _resolve(self, control: ControlIdentity) -> str:
        self._require_expected_origin()
        token = self._page.resolve_control(control)
        if token is None:
            raise DomActionError("report control is not uniquely available")
        return token


class DocumentDomActions(_BaseDomActions[DocumentControlIdentity]):
    def _resolve(self, control: DocumentControlIdentity) -> str:
        self._require_expected_origin()
        resolver = getattr(self._page, "resolve_document_control", None)
        if resolver is None:
            raise DomActionError("report document control is unavailable")
        token = resolver(control)
        if token is None:
            raise DomActionError("report control is not uniquely available")
        return token
