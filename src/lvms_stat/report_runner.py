from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from lvms_stat.browser_session import open_owned_browser
from lvms_stat.cdp import CdpConnection, BrowserPage
from lvms_stat.config import AppConfig, load_app_config
from lvms_stat.dom_actions import DomActions
from lvms_stat.downloads import CsvArrivalDetector, DownloadStatus
from lvms_stat.report_contract import (
    ReportContract,
    discover_report_contract,
    load_contract,
    save_contract,
)
from lvms_stat.report_job import ReportJob, load_report_jobs
from lvms_stat.workflow import ControlIdentity


@dataclass(frozen=True)
class RunnerDependencies:
    config_load: Callable[[Path, Path], AppConfig]
    jobs_load: Callable[[Path], tuple[ReportJob, ...]]
    contract_load: Callable[[Path, Path], ReportContract]
    contract_discover: Callable[[Any, str], ReportContract]
    contract_save: Callable[[ReportContract, Path], Path]
    browser_open: Callable[[Path], Any]
    connection_open: Callable[[Any], Any]
    page_factory: Callable[[Any], Any]
    actions_factory: Callable[[Any, str], Any]
    detector_factory: Callable[[Path], Any]
    clock: Callable[[], float]
    sleeper: Callable[[float], None]


def _default_dependencies() -> RunnerDependencies:
    return RunnerDependencies(
        config_load=lambda path, root: load_app_config(path, repository_root=root),
        jobs_load=load_report_jobs,
        contract_load=load_contract,
        contract_discover=discover_report_contract,
        contract_save=save_contract,
        browser_open=open_owned_browser,
        connection_open=CdpConnection.open,
        page_factory=BrowserPage,
        actions_factory=DomActions,
        detector_factory=CsvArrivalDetector,
        clock=time.monotonic,
        sleeper=time.sleep,
    )


def _close_owned(connection: Any | None, edge: Any | None) -> bool:
    failed = False
    for resource in (connection, edge):
        if resource is None:
            continue
        try:
            resource.close()
        except Exception:
            failed = True
    return failed


def _open_page(config: AppConfig, dependencies: RunnerDependencies) -> tuple[Any, Any, Any]:
    opened = dependencies.browser_open(config.profile_directory)
    connection: Any | None = None
    try:
        connection = dependencies.connection_open(opened.target)
        page = dependencies.page_factory(connection)
        page.navigate(config.landing_url, config.expected_origin, timeout_seconds=120)
        return opened.edge, connection, page
    except Exception:
        _close_owned(connection, opened.edge)
        raise


def discover_report(
    config_path: Path,
    *,
    dependencies: RunnerDependencies | None = None,
    output: TextIO | None = None,
    input_func: Callable[[str], str] = input,
    repository_root: Path | None = None,
) -> int:
    active = dependencies or _default_dependencies()
    stream = output or sys.stdout
    root = repository_root or Path(__file__).resolve().parents[2]
    edge: Any | None = None
    connection: Any | None = None
    result = 2
    try:
        config = active.config_load(config_path, root)
        edge, connection, page = _open_page(config, active)
        stream.write(
            "Open the defined-report form without patient or sample tables. "
            "No report will be exported.\n"
        )
        if input_func("Type DISCOVER to save the safe field contract: ") != "DISCOVER":
            stream.write("Contract discovery cancelled.\n")
            result = 130
        else:
            contract = active.contract_discover(page, config.expected_origin)
            active.contract_save(contract, config.contract_directory)
            stream.write("Report contract saved locally.\n")
            result = 0
    except KeyboardInterrupt:
        stream.write("Contract discovery cancelled.\n")
        result = 130
    except Exception:
        stream.write("Contract discovery failed safely.\n")
        result = 2
    finally:
        if _close_owned(connection, edge):
            stream.write("Contract discovery cleanup did not complete.\n")
            result = 2
    return result


def _select_job(jobs: tuple[ReportJob, ...], job_key: str) -> ReportJob:
    matches = [job for job in jobs if job.job_key == job_key]
    if len(matches) != 1:
        raise ValueError("report job was not uniquely available")
    return matches[0]


def _write_review(stream: TextIO, job: ReportJob) -> None:
    review = job.review()
    stream.write(f"Job: {review.job_key}\n")
    stream.write(f"Report ID: {review.report_id}\n")
    stream.write(f"Analysis count: {review.analysis_count}\n")
    stream.write(f"Interval: {review.created_from} to {review.created_to}\n")


def _wait_available(
    page: Any,
    expected_origin: str,
    control: ControlIdentity,
    dependencies: RunnerDependencies,
    *,
    timeout_seconds: float = 20,
) -> None:
    deadline = dependencies.clock() + timeout_seconds
    while dependencies.clock() < deadline:
        if page.current_origin() != expected_origin:
            raise RuntimeError("unexpected report origin")
        if page.resolve_control(control) is not None:
            return
        dependencies.sleeper(0.1)
    raise TimeoutError("report control did not become available")


def _populate(
    page: Any,
    actions: Any,
    expected_origin: str,
    contract: ReportContract,
    job: ReportJob,
    dependencies: RunnerDependencies,
) -> None:
    _wait_available(page, expected_origin, contract.report_type, dependencies)
    actions.choose_text(contract.report_type, job.report_type)
    _wait_available(page, expected_origin, contract.category, dependencies)
    actions.choose_text(contract.category, job.category)
    _wait_available(page, expected_origin, contract.report_id, dependencies)
    actions.choose_text(contract.report_id, job.report_id)
    _wait_available(page, expected_origin, contract.analysis_codes, dependencies)
    actions.replace_text(contract.analysis_codes, job.analysis_text())
    created_from, created_to = job.interval.as_lvms()
    actions.replace_text(contract.created_from, created_from)
    actions.replace_text(contract.created_to, created_to)


def _wait_for_csv(
    detector: Any,
    dependencies: RunnerDependencies,
    timeout_seconds: float,
) -> None:
    deadline = dependencies.clock() + timeout_seconds
    while dependencies.clock() < deadline:
        status = detector.poll()
        if status is DownloadStatus.DETECTED:
            return
        if status in {DownloadStatus.AMBIGUOUS, DownloadStatus.MISSING}:
            raise RuntimeError("download integrity failed")
        dependencies.sleeper(0.5)
    raise TimeoutError("report download timed out")


def run_report_job(
    config_path: Path,
    jobs_path: Path,
    contract_path: Path,
    job_key: str,
    *,
    dependencies: RunnerDependencies | None = None,
    output: TextIO | None = None,
    input_func: Callable[[str], str] = input,
    repository_root: Path | None = None,
    timeout_seconds: float = 600,
) -> int:
    active = dependencies or _default_dependencies()
    stream = output or sys.stdout
    root = repository_root or Path(__file__).resolve().parents[2]
    edge: Any | None = None
    connection: Any | None = None
    result = 2
    try:
        if not 1 <= timeout_seconds <= 3600:
            raise ValueError("report timeout is invalid")
        config = active.config_load(config_path, root)
        job = _select_job(active.jobs_load(jobs_path), job_key)
        contract = active.contract_load(contract_path, config.contract_directory)
        edge, connection, page = _open_page(config, active)
        actions = active.actions_factory(page, config.expected_origin)
        _populate(page, actions, config.expected_origin, contract, job, active)
        _write_review(stream, job)
        if input_func("Type EXPORT to create the CSV: ") != "EXPORT":
            stream.write("Report export cancelled.\n")
            result = 130
        else:
            page.configure_downloads(config.download_directory)
            detector = active.detector_factory(config.download_directory)
            detector.start()
            actions.activate(contract.export)
            _wait_for_csv(detector, active, timeout_seconds)
            stream.write("Report download: one completed CSV detected.\n")
            result = 0
    except KeyboardInterrupt:
        stream.write("Report export cancelled.\n")
        result = 130
    except Exception:
        stream.write("Report run failed safely.\n")
        result = 2
    finally:
        if _close_owned(connection, edge):
            stream.write("Report cleanup did not complete.\n")
            result = 2
    return result
