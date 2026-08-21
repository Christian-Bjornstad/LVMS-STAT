from __future__ import annotations

import io
import tempfile
import unittest
from datetime import date
from pathlib import Path

from lvms_stat.browser_session import OwnedBrowserStart
from lvms_stat.cdp import PageIdentity, PageTarget
from lvms_stat.config import AppConfig
from lvms_stat.downloads import DownloadStatus
from lvms_stat.report_contract import ReportContract
from lvms_stat.report_job import ReportInterval, ReportJob
from lvms_stat.report_runner import RunnerDependencies, discover_report, run_report_job
from lvms_stat.workflow import ControlIdentity


class FakeEdge:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakePage:
    def __init__(self) -> None:
        self.download_directory: Path | None = None

    def navigate(self, url: str, origin: str, *, timeout_seconds: float) -> PageIdentity:
        del url, timeout_seconds
        return PageIdentity(origin, "LVMS")

    def configure_downloads(self, directory: Path) -> None:
        self.download_directory = directory

    def current_origin(self) -> str:
        return "https://lvms.example.invalid"

    def resolve_control(self, control: ControlIdentity) -> str:
        return f"token-for-{control.element_id}"


class RecordingActions:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str] | tuple[str, str]] = []

    def choose_text(self, control: ControlIdentity, text: str) -> None:
        self.calls.append(("choose", control.element_id, text))

    def replace_text(self, control: ControlIdentity, text: str) -> None:
        self.calls.append(("replace", control.element_id, text))

    def activate(self, control: ControlIdentity) -> None:
        self.calls.append(("activate", control.element_id))


class DetectedCsv:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.started = False

    def start(self) -> None:
        self.started = True

    def poll(self) -> DownloadStatus:
        return DownloadStatus.DETECTED


def control(name: str, tag: str = "INPUT") -> ControlIdentity:
    return ControlIdentity(tag, element_id=name, locator=(f"{tag.lower()}#{name}",))


def contract() -> ReportContract:
    return ReportContract(
        report_type=control("report_type", "SELECT"),
        category=control("category", "SELECT"),
        report_id=control("report_id", "SELECT"),
        analysis_codes=control("analysis_codes"),
        created_from=control("created_from"),
        created_to=control("created_to"),
        export=control("export", "BUTTON"),
    )


def job() -> ReportJob:
    return ReportJob(
        job_key="synthetic_ordered",
        report_type="TYPE_A",
        category="CATEGORY_A",
        report_id="REPORT-A",
        analysis_codes=("ANALYSIS-A", "ANALYSIS-B"),
        interval=ReportInterval(date(2026, 1, 1), date(2026, 8, 21)),
        output_stem="synthetic_ordered",
    )


class ReportRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name).resolve()
        self.config = AppConfig(
            "https://lvms.example.invalid/",
            "https://lvms.example.invalid",
            root / "profile",
            root / "downloads",
            root / "workflows",
            root / "contracts",
        )
        self.edge = FakeEdge()
        self.connection = FakeConnection()
        self.page = FakePage()
        self.actions = RecordingActions()
        self.saved = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def dependencies(self) -> RunnerDependencies:
        def save(found: ReportContract, directory: Path) -> Path:
            self.assertEqual(found, contract())
            self.assertEqual(directory, self.config.contract_directory)
            self.saved += 1
            return directory / "opaque.json"

        return RunnerDependencies(
            config_load=lambda path, repository_root: self.config,
            jobs_load=lambda path: (job(),),
            contract_load=lambda path, directory: contract(),
            contract_discover=lambda page, origin: contract(),
            contract_save=save,
            browser_open=lambda profile: OwnedBrowserStart(
                self.edge,
                PageTarget("page", "ws://127.0.0.1:49152/devtools/page/page", 49152),
            ),
            connection_open=lambda target: self.connection,
            page_factory=lambda connection: self.page,
            actions_factory=lambda page, origin: self.actions,
            detector_factory=DetectedCsv,
            clock=lambda: 0.0,
            sleeper=lambda seconds: None,
        )

    def test_gate_a_discovers_contract_and_stops_without_export(self) -> None:
        result = discover_report(
            Path("config.json"),
            dependencies=self.dependencies(),
            output=io.StringIO(),
            input_func=lambda prompt: "DISCOVER",
        )

        self.assertEqual(result, 0)
        self.assertEqual(self.actions.calls, [])
        self.assertEqual(self.saved, 1)
        self.assertTrue(self.edge.closed)
        self.assertTrue(self.connection.closed)

    def test_gate_b_requires_exact_export_confirmation(self) -> None:
        output = io.StringIO()
        result = run_report_job(
            Path("config.json"),
            Path("jobs.json"),
            Path("contract.json"),
            "synthetic_ordered",
            dependencies=self.dependencies(),
            output=output,
            input_func=lambda prompt: "yes",
        )

        self.assertEqual(result, 130)
        self.assertNotIn(("activate", "export"), self.actions.calls)
        self.assertNotIn("ANALYSIS-A", output.getvalue())

    def test_gate_b_populates_allowlisted_fields_and_detects_one_csv(self) -> None:
        output = io.StringIO()
        result = run_report_job(
            Path("config.json"),
            Path("jobs.json"),
            Path("contract.json"),
            "synthetic_ordered",
            dependencies=self.dependencies(),
            output=output,
            input_func=lambda prompt: "EXPORT",
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            self.actions.calls,
            [
                ("choose", "report_type", "TYPE_A"),
                ("choose", "category", "CATEGORY_A"),
                ("choose", "report_id", "REPORT-A"),
                ("replace", "analysis_codes", "ANALYSIS-A,ANALYSIS-B"),
                ("replace", "created_from", "01.01.2026"),
                ("replace", "created_to", "21.08.2026"),
                ("activate", "export"),
            ],
        )
        self.assertEqual(
            output.getvalue().splitlines()[-1],
            "Report download: one completed CSV detected.",
        )
        self.assertNotIn("ANALYSIS-A", output.getvalue())


if __name__ == "__main__":
    unittest.main()
