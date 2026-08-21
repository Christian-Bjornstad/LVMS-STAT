from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

import websocket

from lvms_stat.edge import EPHEMERAL_PORT_MAX, EPHEMERAL_PORT_MIN
from lvms_stat.inspection import (
    CONTROL_INSPECTION_SCRIPT,
    InspectionError,
    sanitize_controls,
)


MAX_DISCOVERY_BYTES = 64 * 1024
MAX_CDP_MESSAGE_CHARS = 1024 * 1024


class CdpError(RuntimeError):
    """The local Edge DevTools connection failed safely."""


class CdpProtocolError(CdpError):
    """Edge returned malformed or rejected DevTools data."""


class CdpTimeout(CdpError):
    """A bounded DevTools operation did not finish in time."""


class UnexpectedOriginError(CdpError):
    """Navigation did not finish on the configured LVMS origin."""


@dataclass(frozen=True)
class PageTarget:
    target_id: str
    websocket_url: str
    port: int


@dataclass(frozen=True)
class PageIdentity:
    origin: str
    title: str


def _validate_ephemeral_port(port: int) -> None:
    if not isinstance(port, int) or not EPHEMERAL_PORT_MIN <= port <= EPHEMERAL_PORT_MAX:
        raise CdpProtocolError("DevTools port is not ephemeral")


def discover_page(
    port: int,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> PageTarget:
    _validate_ephemeral_port(port)
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/json/list",
        method="GET",
        headers={"Accept": "application/json"},
    )
    try:
        with opener(request, timeout=2) as response:
            payload_bytes = response.read(MAX_DISCOVERY_BYTES + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise CdpTimeout("Edge remote debugging is not available") from exc

    if len(payload_bytes) > MAX_DISCOVERY_BYTES:
        raise CdpProtocolError("Edge discovery response is too large")
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CdpProtocolError("Edge discovery response is invalid") from exc
    if not isinstance(payload, list):
        raise CdpProtocolError("Edge discovery response is invalid")

    for item in payload:
        if not isinstance(item, dict) or item.get("type") != "page":
            continue
        target_id = item.get("id")
        websocket_url = item.get("webSocketDebuggerUrl")
        if not isinstance(target_id, str) or not isinstance(websocket_url, str):
            raise CdpProtocolError("Edge returned an unsafe page target")
        parsed = urlsplit(websocket_url)
        try:
            target_port = parsed.port
        except ValueError as exc:
            raise CdpProtocolError("Edge returned an unsafe page target") from exc
        if (
            parsed.scheme != "ws"
            or parsed.hostname != "127.0.0.1"
            or target_port != port
            or not parsed.path.startswith("/devtools/page/")
        ):
            raise CdpProtocolError("Edge returned an unsafe page target")
        return PageTarget(target_id=target_id, websocket_url=websocket_url, port=port)

    raise CdpTimeout("Edge has not created a page target")


def wait_for_page_target(
    port: int,
    *,
    timeout_seconds: float = 20,
    discover: Callable[[int], PageTarget] = discover_page,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> PageTarget:
    deadline = clock() + timeout_seconds
    while clock() < deadline:
        try:
            return discover(port)
        except CdpTimeout:
            sleep(0.2)
    raise CdpTimeout("Edge connection timed out")


class CdpConnection:
    def __init__(self, socket: Any) -> None:
        self._socket = socket
        self._next_id = 1
        self._pending: dict[int, dict[str, object]] = {}
        self._closed = False

    @classmethod
    def open(
        cls,
        target: PageTarget,
        *,
        socket_factory: Callable[..., Any] = websocket.create_connection,
    ) -> "CdpConnection":
        _validate_ephemeral_port(target.port)
        parsed = urlsplit(target.websocket_url)
        if parsed.hostname != "127.0.0.1" or parsed.port != target.port:
            raise CdpProtocolError("Edge returned an unsafe page target")
        try:
            socket = socket_factory(
                target.websocket_url,
                timeout=10,
                origin=f"http://127.0.0.1:{target.port}",
                enable_multithread=False,
            )
        except Exception as exc:
            raise CdpTimeout("Edge DevTools WebSocket is not available") from exc
        return cls(socket)

    def call(
        self,
        method: str,
        params: dict[str, object] | None = None,
        *,
        timeout_seconds: float = 10,
    ) -> dict[str, object]:
        if self._closed:
            raise CdpProtocolError("Edge DevTools connection is closed")
        if not method or timeout_seconds <= 0:
            raise CdpProtocolError("invalid DevTools command")

        command_id = self._next_id
        self._next_id += 1
        command: dict[str, object] = {"id": command_id, "method": method}
        if params is not None:
            command["params"] = params

        try:
            self._socket.send(json.dumps(command, separators=(",", ":")))
            self._socket.settimeout(timeout_seconds)
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                pending = self._pending.pop(command_id, None)
                if pending is not None:
                    return self._command_result(method, pending)

                raw_message = self._socket.recv()
                if not isinstance(raw_message, str) or len(raw_message) > MAX_CDP_MESSAGE_CHARS:
                    raise CdpProtocolError("Edge returned an invalid DevTools response")
                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError as exc:
                    raise CdpProtocolError("Edge returned an invalid DevTools response") from exc
                if not isinstance(message, dict):
                    raise CdpProtocolError("Edge returned an invalid DevTools response")
                response_id = message.get("id")
                if isinstance(response_id, int):
                    if response_id == command_id:
                        return self._command_result(method, message)
                    self._pending[response_id] = message
                # Asynchronous events are intentionally ignored in this slice.
        except CdpError:
            raise
        except (TimeoutError, websocket.WebSocketTimeoutException) as exc:
            raise CdpTimeout(f"Edge timed out during {method}") from exc
        except Exception as exc:
            raise CdpProtocolError(f"Edge failed during {method}") from exc

        raise CdpTimeout(f"Edge timed out during {method}")

    @staticmethod
    def _command_result(method: str, message: dict[str, object]) -> dict[str, object]:
        if "error" in message:
            raise CdpProtocolError(f"Edge rejected {method}")
        result = message.get("result", {})
        if not isinstance(result, dict):
            raise CdpProtocolError(f"Edge returned an invalid result for {method}")
        return result

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._socket.close()
        except Exception:
            pass


class BrowserPage:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def _evaluate(self, expression: str, *, timeout_seconds: float) -> object:
        response = self._connection.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": False,
            },
            timeout_seconds=timeout_seconds,
        )
        remote_object = response.get("result")
        if not isinstance(remote_object, dict) or "value" not in remote_object:
            raise CdpProtocolError("Edge returned an invalid evaluation result")
        return remote_object["value"]

    def evaluate_safe(self, expression: str, *, timeout_seconds: float = 2) -> object:
        return self._evaluate(expression, timeout_seconds=timeout_seconds)

    def current_origin(self) -> str:
        origin = self._evaluate("location.origin", timeout_seconds=2)
        if not isinstance(origin, str):
            raise CdpProtocolError("Edge returned an invalid origin")
        return origin

    def configure_downloads(self, directory: Path) -> None:
        if not directory.is_absolute():
            raise CdpProtocolError("download directory must be absolute")
        resolved = directory.resolve()
        try:
            resolved.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CdpProtocolError("download directory is unavailable") from exc
        self._connection.call(
            "Browser.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(resolved)},
            timeout_seconds=5,
        )

    def navigate(
        self,
        landing_url: str,
        expected_origin: str,
        *,
        timeout_seconds: float = 30,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> PageIdentity:
        self._connection.call("Page.enable", timeout_seconds=timeout_seconds)
        self._connection.call("Runtime.enable", timeout_seconds=timeout_seconds)
        navigation = self._connection.call(
            "Page.navigate",
            {"url": landing_url},
            timeout_seconds=timeout_seconds,
        )
        if navigation.get("errorText"):
            raise CdpProtocolError("Edge navigation failed")

        deadline = clock() + timeout_seconds
        last_origin: object = None
        while clock() < deadline:
            state = self._evaluate(
                "document.readyState", timeout_seconds=min(2, timeout_seconds)
            )
            last_origin = self._evaluate("location.origin", timeout_seconds=2)
            if state in {"interactive", "complete"} and last_origin == expected_origin:
                break
            sleep(0.1)
        else:
            if last_origin != expected_origin:
                raise UnexpectedOriginError("Edge reached an unexpected origin")
            raise CdpTimeout("Edge navigation timed out")

        title = self._evaluate("document.title", timeout_seconds=2)
        safe_title = title.strip()[:120] if isinstance(title, str) else ""
        return PageIdentity(origin=expected_origin, title=safe_title)

    def inspect_controls(self, expected_origin: str) -> list[dict[str, str]]:
        origin = self._evaluate("location.origin", timeout_seconds=2)
        if origin != expected_origin:
            raise UnexpectedOriginError("Edge reached an unexpected origin")
        raw_controls = self._evaluate(CONTROL_INSPECTION_SCRIPT, timeout_seconds=10)
        try:
            return sanitize_controls(raw_controls)
        except InspectionError as exc:
            raise CdpProtocolError("Edge returned unsafe control metadata") from exc
