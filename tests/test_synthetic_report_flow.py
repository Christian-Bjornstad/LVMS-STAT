from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from lvms_stat.browser_session import OwnedBrowserStart
from lvms_stat.cdp import PageIdentity, PageTarget
from lvms_stat.config import AppConfig
from lvms_stat.dom_actions import DomActions
from lvms_stat.downloads import CsvArrivalDetector
from lvms_stat.report_contract import discover_report_contract
from lvms_stat.report_contract import load_contract, save_contract
from lvms_stat.report_job import ReportInterval, ReportJob
from lvms_stat.report_runner import RunnerDependencies
from lvms_stat.report_runner import run_report_job
from lvms_stat.workflow import ControlIdentity


def _identity(tag: str, element_id: str, label: str) -> dict[str, object]:
    return {
        "tag": tag,
        "type": "",
        "id": element_id,
        "name": "",
        "role": "",
        "label": label,
        "locator": [f"{tag.lower()}#{element_id}"],
    }


class SyntheticEdge:
    def __init__(self, harness: "SyntheticReportHarness") -> None:
        self.harness = harness

    def close(self) -> None:
        self.harness.edge_closed = True


class SyntheticConnection:
    def __init__(self, harness: "SyntheticReportHarness") -> None:
        self.harness = harness

    def close(self) -> None:
        self.harness.connection_closed = True


class SyntheticPage:
    def __init__(self, harness: "SyntheticReportHarness", html: str) -> None:
        self.harness = harness
        self.html = html
        self.focused = ""
        self.values: dict[str, str] = {}
        self.tokens: dict[str, str] = {}

    def navigate(self, url: str, origin: str, *, timeout_seconds: float) -> PageIdentity:
        del url, timeout_seconds
        return PageIdentity(origin, "Synthetic LVMS")

    def current_origin(self) -> str:
        return self.harness.expected_origin

    def evaluate_safe(self, expression: str, *, timeout_seconds: float = 2) -> object:
        del expression, timeout_seconds
        return {
            "report_type": _identity("SELECT", "report-type", "Report type"),
            "category": _identity("SELECT", "category", "Category"),
            "report_id": _identity("SELECT", "report-id", "Report id"),
            "analysis_codes": _identity("INPUT", "analyses", "Analyses"),
            "created_from": _identity("INPUT", "created-from", "Created from"),
            "created_to": _identity("INPUT", "created-to", "Created to"),
            "export": _identity("BUTTON", "export", ""),
        }

    def configure_downloads(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)

    def resolve_control(self, control: ControlIdentity) -> str | None:
        marker = f'id="{control.element_id}"'
        if marker not in self.html:
            return None
        token = f"token-{control.element_id}"
        self.tokens[token] = control.element_id
        return token

    def focus_control(self, token: str) -> None:
        self.focused = self.tokens[token]

    def replace_focused_text(self, text: str) -> None:
        self.values[self.focused] = text

    def choose_native_option(self, token: str, text: str) -> bool:
        self.values[self.tokens[token]] = text
        return True

    def press_key(self, key: str) -> None:
        raise AssertionError(f"synthetic native selects must not press {key}")

    def activate_control(self, token: str) -> None:
        if self.tokens[token] != "export":
            raise AssertionError("only the synthetic export control may be activated")
        destination = self.harness.config.download_directory / "synthetic.csv"
        destination.write_text("metric,count\nsynthetic,1\n", encoding="utf-8")


@dataclass
class SyntheticReportHarness:
    root: Path
    expected_origin: str
    config: AppConfig
    page: SyntheticPage
    edge_closed: bool = False
    connection_closed: bool = False
    csv_open_count: int = 0
    csv_read_count: int = 0

    @classmethod
    def from_fixture(cls, fixture: Path, root: Path) -> "SyntheticReportHarness":
        html = fixture.read_text(encoding="utf-8")
        expected_origin = "https://lvms.example.invalid"
        config = AppConfig(
            f"{expected_origin}/",
            expected_origin,
            root / "profile",
            root / "downloads",
            root / "workflows",
            root / "contracts",
        )
        harness = cls(root, expected_origin, config, page=None)  # type: ignore[arg-type]
        harness.page = SyntheticPage(harness, html)
        return harness

    @property
    def config_path(self) -> Path:
        return self.root / "config.json"

    @property
    def jobs_path(self) -> Path:
        return self.root / "jobs.json"

    def save_contract(self, contract: object) -> Path:
        return save_contract(contract, self.config.contract_directory)  # type: ignore[arg-type]

    def dependencies(self) -> RunnerDependencies:
        edge = SyntheticEdge(self)
        connection = SyntheticConnection(self)
        ticks = {"value": 0.0}

        def clock() -> float:
            ticks["value"] += 0.1
            return ticks["value"]

        synthetic_job = ReportJob(
            "synthetic_ordered",
            "TYPE_A",
            "CATEGORY_A",
            "REPORT-A",
            ("ANALYSIS-A", "ANALYSIS-B"),
            ReportInterval(date(2026, 1, 1), date(2026, 8, 21)),
            "synthetic_ordered",
        )
        return RunnerDependencies(
            config_load=lambda path, repository_root: self.config,
            jobs_load=lambda path: (synthetic_job,),
            contract_load=load_contract,
            contract_discover=discover_report_contract,
            contract_save=save_contract,
            browser_open=lambda profile: OwnedBrowserStart(
                edge,
                PageTarget("page", "ws://127.0.0.1:49152/devtools/page/page", 49152),
            ),
            connection_open=lambda target: connection,
            page_factory=lambda active_connection: self.page,
            actions_factory=DomActions,
            detector_factory=CsvArrivalDetector,
            clock=clock,
            sleeper=lambda seconds: None,
        )


def test_synthetic_defined_report_flow_never_opens_or_reads_csv(tmp_path: Path) -> None:
    harness = SyntheticReportHarness.from_fixture(
        Path("tests/fixtures/defined_reports.html"), tmp_path.resolve()
    )
    contract = discover_report_contract(harness.page, harness.expected_origin)
    result = run_report_job(
        harness.config_path,
        harness.jobs_path,
        harness.save_contract(contract),
        "synthetic_ordered",
        dependencies=harness.dependencies(),
        output=io.StringIO(),
        input_func=lambda prompt: "EXPORT",
    )

    assert result == 0
    assert harness.csv_open_count == 0
    assert harness.csv_read_count == 0
    assert harness.edge_closed
    assert harness.connection_closed
    assert harness.page.values == {
        "report-type": "TYPE_A",
        "category": "CATEGORY_A",
        "report-id": "REPORT-A",
        "analyses": "ANALYSIS-A,ANALYSIS-B",
        "created-from": "01.01.2026",
        "created-to": "21.08.2026",
    }
