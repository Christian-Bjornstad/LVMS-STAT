from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from lvms_stat.batch_form import BatchReportForm
from lvms_stat.batch_navigation import (
    DefinedReportsNavigator,
    DefinedReportsPage,
    discover_defined_reports_page,
)
from lvms_stat.browser_runtime import close_owned, open_page
from lvms_stat.browser_session import open_owned_browser
from lvms_stat.cdp import BrowserPage, CdpConnection
from lvms_stat.config import AppConfig, load_app_config
from lvms_stat.dom_actions import DocumentDomActions
from lvms_stat.downloads import (
    CsvArrivalDetector,
    DownloadStatus,
    finalize_csv,
)
from lvms_stat.report_job import (
    ReportJob,
    batch_filename,
    load_report_jobs,
    select_batch_jobs,
)


@dataclass(frozen=True)
class BatchRunnerDependencies:
    config_load: Callable[[Path, Path], AppConfig]
    jobs_load: Callable[[Path], tuple[ReportJob, ...]]
    browser_open: Callable[[Path], Any]
    connection_open: Callable[[Any], Any]
    page_factory: Callable[[Any], Any]
    actions_factory: Callable[[Any, str], Any]
    navigator_factory: Callable[[str, Callable[[], float], Callable[[float], None]], Any]
    form_factory: Callable[
        [Any, Any, str, Callable[[], float], Callable[[float], None]], Any
    ]
    contract_discover: Callable[[Any, str], DefinedReportsPage | None]
    detector_factory: Callable[[Path], Any]
    finalizer: Callable[[Path, Path, str], Path]
    clock: Callable[[], float]
    sleeper: Callable[[float], None]


def _default_dependencies() -> BatchRunnerDependencies:
    return BatchRunnerDependencies(
        config_load=lambda path, root: load_app_config(path, repository_root=root),
        jobs_load=load_report_jobs,
        browser_open=open_owned_browser,
        connection_open=CdpConnection.open,
        page_factory=BrowserPage,
        actions_factory=DocumentDomActions,
        navigator_factory=lambda origin, clock, sleeper: DefinedReportsNavigator(
            origin, clock=clock, sleep=sleeper
        ),
        form_factory=lambda page, actions, origin, clock, sleeper: BatchReportForm(
            page, actions, origin, clock=clock, sleep=sleeper
        ),
        contract_discover=discover_defined_reports_page,
        detector_factory=CsvArrivalDetector,
        finalizer=finalize_csv,
        clock=time.monotonic,
        sleeper=time.sleep,
    )


def _write_review(stream: TextIO, job: ReportJob) -> None:
    review = job.review()
    stream.write(f"Job: {review.job_key}\n")
    stream.write(f"Report ID: {review.report_id}\n")
    stream.write(f"Analysis count: {review.analysis_count}\n")
    stream.write(f"Interval: {review.created_from} to {review.created_to}\n")


def _wait_for_page(
    page: Any,
    expected_origin: str,
    dependencies: BatchRunnerDependencies,
    *,
    timeout_seconds: float = 20,
) -> DefinedReportsPage:
    deadline = dependencies.clock() + timeout_seconds
    while dependencies.clock() < deadline:
        contract = dependencies.contract_discover(page, expected_origin)
        if contract is not None:
            return contract
        dependencies.sleeper(0.1)
    raise TimeoutError("Defined Reports page did not become ready")


def _wait_for_csv(
    detector: Any,
    dependencies: BatchRunnerDependencies,
    timeout_seconds: float,
) -> Path:
    deadline = dependencies.clock() + timeout_seconds
    while dependencies.clock() < deadline:
        status = detector.poll()
        if status is DownloadStatus.DETECTED:
            detected = detector.detected_path()
            if not isinstance(detected, Path):
                raise RuntimeError("completed CSV was unavailable")
            return detected
        if status in {DownloadStatus.AMBIGUOUS, DownloadStatus.MISSING}:
            raise RuntimeError("download integrity failed")
        dependencies.sleeper(0.5)
    raise TimeoutError("report download timed out")


def run_report_batch(
    config_path: Path,
    jobs_path: Path,
    job_keys: tuple[str, ...],
    *,
    dependencies: BatchRunnerDependencies | None = None,
    output: TextIO | None = None,
    repository_root: Path | None = None,
    timeout_seconds: float = 600,
) -> int:
    active = dependencies or _default_dependencies()
    stream = output or sys.stdout
    root = repository_root or Path(__file__).resolve().parents[2]
    edge: Any | None = None
    connection: Any | None = None
    current_job: str | None = None
    result = 2
    try:
        if not 1 <= timeout_seconds <= 3600:
            raise ValueError("report timeout is invalid")
        config = active.config_load(config_path, root)
        jobs = select_batch_jobs(active.jobs_load(jobs_path), job_keys)
        filenames = tuple(batch_filename(job) for job in jobs)
        if any((config.download_directory / name).exists() for name in filenames):
            raise RuntimeError("batch destination already exists")

        edge, connection, page = open_page(config, active)
        page.configure_downloads(config.download_directory)
        actions = active.actions_factory(page, config.expected_origin)
        navigator = active.navigator_factory(
            config.expected_origin, active.clock, active.sleeper
        )
        navigator.reach(page, actions)
        form = active.form_factory(
            page,
            actions,
            config.expected_origin,
            active.clock,
            active.sleeper,
        )

        for job, filename in zip(jobs, filenames, strict=True):
            current_job = job.job_key
            contract = _wait_for_page(page, config.expected_origin, active)
            actions.activate(contract.clear)
            contract = _wait_for_page(page, config.expected_origin, active)
            form.populate(contract, job)
            _write_review(stream, job)
            contract = _wait_for_page(page, config.expected_origin, active)
            detector = active.detector_factory(config.download_directory)
            detector.start()
            actions.activate(contract.export)
            source = _wait_for_csv(detector, active, timeout_seconds)
            active.finalizer(source, config.download_directory, filename)
            stream.write(f"Batch job completed: {job.job_key} -> {filename}\n")
        result = 0
    except KeyboardInterrupt:
        stream.write("Batch cancelled.\n")
        result = 130
    except Exception:
        if current_job is None:
            stream.write("Batch failed safely.\n")
        else:
            stream.write(f"Batch job failed safely: {current_job}.\n")
        result = 2
    finally:
        if close_owned(connection, edge):
            stream.write("Batch cleanup did not complete.\n")
            result = 2
    return result
