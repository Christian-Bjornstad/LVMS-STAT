from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from lvms_stat.cdp import CdpTimeout, PageIdentity, PageTarget
from lvms_stat.probe import (
    CapabilityCode,
    CapabilityResult,
    ProbeDependencies,
    classify_probe_error,
    run_probe,
)
from lvms_stat.cdp import wait_for_page_target


class FakeEdge:
    def __init__(self) -> None:
        self.port = 49152
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakePage:
    def __init__(
        self,
        identity: PageIdentity,
        controls: list[dict[str, str]] | None = None,
    ) -> None:
        self.identity = identity
        self.controls = controls or []
        self.inspection_calls = 0
        self.navigation_timeout: float | None = None

    def navigate(
        self,
        landing_url: str,
        expected_origin: str,
        *,
        timeout_seconds: float = 30,
    ) -> PageIdentity:
        del landing_url, expected_origin
        self.navigation_timeout = timeout_seconds
        return self.identity

    def inspect_controls(self, expected_origin: str) -> list[dict[str, str]]:
        del expected_origin
        self.inspection_calls += 1
        return self.controls


class ProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.temp_root = Path(self.temporary_directory.name)
        self.repository_root = self.temp_root / "repository"
        self.repository_root.mkdir()
        self.local_app_data = self.temp_root / "local-app-data"
        self.local_app_data.mkdir()
        self.config_path = self.temp_root / "config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "landing_url": "https://lvms.example.invalid/",
                    "profile_directory": str(self.local_app_data / "edge-profile"),
                }
            ),
            encoding="utf-8",
        )

    def dependencies(
        self,
        *,
        page: FakePage,
        edge: FakeEdge | None = None,
        connection: FakeConnection | None = None,
        target_error: Exception | None = None,
    ) -> tuple[ProbeDependencies, FakeEdge, FakeConnection]:
        fake_edge = edge or FakeEdge()
        fake_connection = connection or FakeConnection()

        def wait_for_target(port: int) -> PageTarget:
            del port
            if target_error is not None:
                raise target_error
            return PageTarget(
                target_id="page-1",
                websocket_url="ws://127.0.0.1:49152/devtools/page/page-1",
                port=49152,
            )

        dependencies = ProbeDependencies(
            edge_start=lambda profile: fake_edge,
            target_wait=wait_for_target,
            connection_open=lambda target: fake_connection,
            page_factory=lambda active_connection: page,
        )
        return dependencies, fake_edge, fake_connection

    def test_probe_reports_only_origin_and_capped_title(self) -> None:
        page = FakePage(PageIdentity("https://lvms.example.invalid", "LVMS"))
        dependencies, edge, connection = self.dependencies(page=page)
        output = io.StringIO()

        result = run_probe(
            self.config_path,
            dependencies=dependencies,
            output=output,
            repository_root=self.repository_root,
            allowed_profile_root=self.local_app_data,
        )

        self.assertEqual(result, 0)
        self.assertEqual(page.navigation_timeout, 120)
        self.assertEqual(
            output.getvalue(),
            "Connected: https://lvms.example.invalid — LVMS\n",
        )
        self.assertTrue(edge.closed)
        self.assertTrue(connection.closed)

    def test_failure_is_sanitized_and_always_closes_child_edge(self) -> None:
        page = FakePage(PageIdentity("https://lvms.example.invalid", "LVMS"))
        dependencies, edge, connection = self.dependencies(
            page=page,
            target_error=CdpTimeout("internal detail"),
        )
        output = io.StringIO()

        result = run_probe(
            self.config_path,
            dependencies=dependencies,
            output=output,
            repository_root=self.repository_root,
            allowed_profile_root=self.local_app_data,
        )

        self.assertEqual(result, 2)
        self.assertEqual(output.getvalue(), "Probe failed: Edge connection timed out.\n")
        self.assertNotIn("internal detail", output.getvalue())
        self.assertTrue(edge.closed)
        self.assertFalse(connection.closed)

    def test_inspect_requires_explicit_confirmation_and_prints_safe_json(self) -> None:
        page = FakePage(
            PageIdentity("https://lvms.example.invalid", "LVMS"),
            controls=[{"tag": "BUTTON", "text": "Export"}],
        )
        dependencies, _, _ = self.dependencies(page=page)
        output = io.StringIO()

        result = run_probe(
            self.config_path,
            inspect=True,
            dependencies=dependencies,
            output=output,
            input_func=lambda prompt: "INSPECT",
            repository_root=self.repository_root,
            allowed_profile_root=self.local_app_data,
        )

        self.assertEqual(result, 0)
        self.assertIn('{"tag": "BUTTON", "text": "Export"}\n', output.getvalue())
        self.assertEqual(page.inspection_calls, 1)

    def test_inspect_cancels_without_exact_confirmation(self) -> None:
        page = FakePage(PageIdentity("https://lvms.example.invalid", "LVMS"))
        dependencies, _, _ = self.dependencies(page=page)

        result = run_probe(
            self.config_path,
            inspect=True,
            dependencies=dependencies,
            output=io.StringIO(),
            input_func=lambda prompt: "yes",
            repository_root=self.repository_root,
            allowed_profile_root=self.local_app_data,
        )

        self.assertEqual(result, 130)
        self.assertEqual(page.inspection_calls, 0)

    def test_target_wait_retries_only_timeout_until_page_exists(self) -> None:
        target = PageTarget(
            target_id="page-1",
            websocket_url="ws://127.0.0.1:49152/devtools/page/page-1",
            port=49152,
        )
        attempts = 0
        sleeps: list[float] = []
        ticks = iter((0.0, 0.0, 0.1))

        def discover(port: int) -> PageTarget:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise CdpTimeout("not ready")
            return target

        result = wait_for_page_target(
            49152,
            timeout_seconds=1,
            discover=discover,
            clock=lambda: next(ticks),
            sleep=sleeps.append,
        )

        self.assertEqual(result, target)
        self.assertEqual(attempts, 2)
        self.assertEqual(sleeps, [0.2])

    def test_capability_error_is_fixed_and_redacted(self) -> None:
        result = classify_probe_error(
            CdpTimeout("ws://127.0.0.1:55555/private")
        )

        self.assertEqual(
            result,
            CapabilityResult(CapabilityCode.CDP_UNAVAILABLE, False),
        )
        self.assertNotIn("55555", result.user_message)


if __name__ == "__main__":
    unittest.main()
