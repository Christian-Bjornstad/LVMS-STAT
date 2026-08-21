# Automatic Three-Report Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically navigate one visible owned Edge session through LVMS Defined Reports, run exactly three explicit local jobs, and finalize three non-overwriting CSV files without reading them.

**Architecture:** Add a batch-only frame-aware control wrapper around the existing sanitized `ControlIdentity`, then build a deterministic navigator and staged form controller on top of `BrowserPage`. A separate batch runner owns orchestration and download finalization while existing probe, recorder, contract, and single-job flows remain unchanged.

**Tech Stack:** Python 3.11+, standard library, `websocket-client`, Microsoft Edge CDP, `pytest`/`unittest`, synthetic in-process browser harness.

**Spec:** `docs/superpowers/specs/2026-08-21-automatic-three-report-batch-design.md`

## Global Constraints

- Run only in one visible LVMS-STAT-owned Edge child; never attach to PowerGate or another existing browser.
- CDP remains bound to `127.0.0.1` on an OS-selected non-privileged port.
- Proceed only on the configured exact expected origin; revalidate it before every state-changing action.
- Search only the top document and accessible same-origin named frames; never store or emit frame URLs.
- Never read form values, tables, grids, report content, CSV content, cookies, storage, headers, or network bodies.
- The batch command itself authorizes all three exports; it has no interactive confirmation.
- Require exactly three distinct local job keys with short explicit dates for the first increment.
- Stop on the first navigation, selector, origin, download, duplicate, or cleanup failure; never retry an export.
- Final CSV names are `<output_stem>__<YYYY-MM-DD>__<YYYY-MM-DD>.csv`; never overwrite or suffix an existing target.
- Do not modify Tkinter or add PyQt6, scheduling, relative dates, backfill, CSV parsing, aggregation, or Power BI behavior.
- Keep real hostnames, report IDs, analysis codes, dates, paths, and CSV files out of Git.

---

### Task 1: Validate the Three-Job Batch and Finalize Downloads Safely

**Files:**
- Modify: `src/lvms_stat/report_job.py`
- Modify: `src/lvms_stat/downloads.py`
- Modify: `tests/test_report_job.py`
- Modify: `tests/test_downloads.py`

**Interfaces:**
- Consumes: `ReportJob`, `ReportInterval`, `CsvArrivalDetector.detected_path()`.
- Produces in `report_job.py`: `select_batch_jobs(jobs: tuple[ReportJob, ...], job_keys: tuple[str, ...]) -> tuple[ReportJob, ...]` and `batch_filename(job: ReportJob) -> str`.
- Produces in `downloads.py`: `finalize_csv(source: Path, directory: Path, filename: str) -> Path`.

- [ ] **Step 1: Write failing batch-selection tests**

```python
def test_select_batch_jobs_preserves_exact_three_key_order():
    jobs = (job("one"), job("two"), job("three"))
    selected = select_batch_jobs(jobs, ("three", "one", "two"))
    assert tuple(item.job_key for item in selected) == ("three", "one", "two")


def test_select_batch_jobs_rejects_wrong_count_duplicates_and_missing_key():
    jobs = (job("one"), job("two"), job("three"))
    for keys in (("one",), ("one", "one", "two"), ("one", "two", "missing")):
        with pytest.raises(ReportJobError):
            select_batch_jobs(jobs, keys)
```

- [ ] **Step 2: Run the job tests and verify RED**

Run: `python -m pytest tests/test_report_job.py -q`

Expected: FAIL because `select_batch_jobs` does not exist.

- [ ] **Step 3: Implement exact three-job selection**

```python
def select_batch_jobs(
    jobs: tuple[ReportJob, ...], job_keys: tuple[str, ...]
) -> tuple[ReportJob, ...]:
    if len(job_keys) != 3 or len(set(job_keys)) != 3:
        raise ReportJobError("batch requires three distinct job keys")
    by_key = {job.job_key: job for job in jobs}
    if any(key not in by_key for key in job_keys):
        raise ReportJobError("batch job was not found")
    selected = tuple(by_key[key] for key in job_keys)
    names = [batch_filename(job) for job in selected]
    if len(set(names)) != len(names):
        raise ReportJobError("batch output targets contain duplicates")
    return selected
```

- [ ] **Step 4: Write failing deterministic-name and non-overwrite tests**

```python
def test_batch_filename_is_deterministic_and_safe():
    assert batch_filename(job("one")) == "one__2026-08-01__2026-08-07.csv"


def test_finalize_csv_moves_without_reading_or_overwriting(tmp_path):
    inbox = tmp_path.resolve()
    source = inbox / "generated.csv"
    source.write_bytes(b"synthetic")
    destination = finalize_csv(source, inbox, "one__2026-08-01__2026-08-07.csv")
    assert destination.is_file()
    assert not source.exists()
    destination.write_bytes(b"existing")
    second = inbox / "second.csv"
    second.write_bytes(b"new")
    with pytest.raises(DownloadError):
        finalize_csv(second, inbox, destination.name)
    assert second.is_file()
    assert destination.read_bytes() == b"existing"
```

- [ ] **Step 5: Run download tests and verify RED**

Run: `python -m pytest tests/test_downloads.py -q`

Expected: FAIL because `batch_filename` and `finalize_csv` do not exist.

- [ ] **Step 6: Implement naming and Windows non-replacing rename**

`batch_filename` formats `ReportInterval` dates as ISO and uses the already validated `output_stem`. `finalize_csv` must require absolute paths, require `source.parent == directory.resolve()`, require a `.csv` source and destination, reject an existing destination before rename, call `source.rename(destination)`, and convert `OSError` to a fixed `DownloadError` without including paths.

- [ ] **Step 7: Run focused and full tests**

Run: `python -m pytest tests/test_report_job.py tests/test_downloads.py -q`

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add -- src/lvms_stat/report_job.py src/lvms_stat/downloads.py tests/test_report_job.py tests/test_downloads.py
git commit -m "feat: add safe three-job output finalization"
```

---

### Task 2: Add Batch-Only Frame-Aware Control Identity

**Files:**
- Create: `src/lvms_stat/batch_controls.py`
- Create: `tests/test_batch_controls.py`
- Modify: `src/lvms_stat/cdp.py`
- Modify: `src/lvms_stat/dom_actions.py`
- Modify: `tests/test_cdp.py`
- Modify: `tests/test_dom_actions.py`

**Interfaces:**
- Consumes: existing `ControlIdentity` and `BrowserPage` token actions.
- Produces: `DocumentControlIdentity(frame: str, control: ControlIdentity)`, `validate_document_control(identity)`, `BrowserPage.resolve_document_control(identity) -> str | None`, and `DocumentDomActions` with `activate`, `replace_text`, and `choose_text`.

- [ ] **Step 1: Write failing identity validation tests**

```python
def test_document_control_accepts_top_and_bounded_named_frame():
    top = validate_document_control(DocumentControlIdentity("top", control("SELECT", "jobtypeselector")))
    framed = validate_document_control(DocumentControlIdentity("_nav_frame1", control("BUTTON", "export")))
    assert top.frame == "top"
    assert framed.frame == "_nav_frame1"


def test_document_control_rejects_url_path_and_empty_frame():
    for frame in ("", "https://frame.invalid", "../frame", "a" * 121):
        with pytest.raises(BatchControlError):
            validate_document_control(DocumentControlIdentity(frame, control("BUTTON", "export")))
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_batch_controls.py -q`

Expected: FAIL because `batch_controls.py` does not exist.

- [ ] **Step 3: Implement the immutable wrapper and strict frame pattern**

Use a full-match pattern `[A-Za-z0-9_-]{1,120}` plus the reserved exact value `top`. Require the wrapped value to be a `ControlIdentity`. Do not change workflow or stored contract schemas.

- [ ] **Step 4: Write failing CDP frame-resolution tests**

```python
def test_resolve_document_control_selects_named_same_origin_frame():
    cdp = FakeCdp([evaluated(1)])
    page = BrowserPage(cdp)
    token = page.resolve_document_control(
        DocumentControlIdentity("_nav_frame1", control("BUTTON", "export"))
    )
    assert token is not None
    expression = cdp.calls[0][1]["expression"]
    assert "contentDocument" in expression
    assert "_nav_frame1" in expression
    assert ".src" not in expression
```

Also add tests for zero/multiple frames, inaccessible `contentDocument`, hidden/disabled/read-only controls, and a top-document identity.

- [ ] **Step 5: Run and verify RED**

Run: `python -m pytest tests/test_cdp.py -q`

Expected: FAIL because `resolve_document_control` does not exist.

- [ ] **Step 6: Implement frame-aware resolution without content reads**

Add a private browser expression that selects `document` for `top`, otherwise filters `iframe,frame` by exact sanitized `id` or `name`, requires one accessible `contentDocument`, and applies the existing exact control matcher inside that document. Store the resolved element in the existing top-window token map. Return only the numeric match count.

Refactor `resolve_control(control)` to call `resolve_document_control(DocumentControlIdentity("top", control))` so existing callers retain behavior.

- [ ] **Step 7: Write failing frame-action tests**

```python
def test_document_actions_revalidate_origin_and_use_document_identity():
    page = RecordingDocumentPage()
    actions = DocumentDomActions(page, "https://lvms.example.invalid")
    actions.activate(DocumentControlIdentity("_nav_frame1", control("BUTTON", "export")))
    assert page.operations == [
        ("origin", "https://lvms.example.invalid"),
        ("resolve_document", "_nav_frame1", "export"),
        ("activate", "safe-token"),
    ]
```

- [ ] **Step 8: Implement `DocumentDomActions` using existing token primitives**

Do not duplicate input dispatch. Only the resolution method differs from `DomActions`. Share private action helpers where clarity improves, but preserve existing public behavior and tests.

- [ ] **Step 9: Run focused and full tests**

Run: `python -m pytest tests/test_batch_controls.py tests/test_cdp.py tests/test_dom_actions.py -q`

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 10: Commit**

```powershell
git add -- src/lvms_stat/batch_controls.py src/lvms_stat/cdp.py src/lvms_stat/dom_actions.py tests/test_batch_controls.py tests/test_cdp.py tests/test_dom_actions.py
git commit -m "feat: add frame-aware batch controls"
```

---

### Task 3: Recognize and Reach the Defined Reports Page Automatically

**Files:**
- Create: `src/lvms_stat/batch_navigation.py`
- Create: `tests/test_batch_navigation.py`
- Modify: `src/lvms_stat/batch_controls.py`

**Interfaces:**
- Consumes: `BrowserPage.evaluate_safe`, `DocumentControlIdentity`, `DocumentDomActions`, expected origin, clock, sleeper.
- Produces: `DefinedReportsPage(job_type, clear, export)`, `discover_defined_reports_page(page, expected_origin) -> DefinedReportsPage | None`, `discover_navigation_anchor(page, expected_origin, label) -> DocumentControlIdentity | None`, and `DefinedReportsNavigator.reach(page, actions) -> DefinedReportsPage`.

- [ ] **Step 1: Write failing structural-page contract tests**

```python
def test_page_requires_all_three_controls_in_exact_documents():
    page = FakeSafePage(page_contract_payload())
    contract = discover_defined_reports_page(page, EXPECTED_ORIGIN)
    assert contract.job_type.frame == "top"
    assert contract.job_type.control.element_id == "jobtypeselector"
    assert contract.clear.frame == "_nav_frame1"
    assert contract.export.control.element_id == "export"


def test_page_rejects_partial_ambiguous_or_wrong_origin_contract():
    for payload in (missing_export_payload(), duplicate_frame_payload()):
        assert discover_defined_reports_page(FakeSafePage(payload), EXPECTED_ORIGIN) is None
    with pytest.raises(BatchNavigationError):
        discover_defined_reports_page(FakeSafePage(page_contract_payload(), OTHER_ORIGIN), EXPECTED_ORIGIN)
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_batch_navigation.py -q`

Expected: FAIL because the navigation module does not exist.

- [ ] **Step 3: Implement bounded page-contract discovery**

The browser script returns only exact structural identity for:

- top `SELECT#jobtypeselector[name=jobtypeselector]`;
- named same-origin frame `_nav_frame1`;
- frame `BUTTON#clear[name=menu][type=button]`;
- frame `BUTTON#export[name=menu][type=button]`.

It must not return option text, values, URLs, frame sources, or surrounding text. The Python sanitizer requires exactly those fields and compatible tags/types.

- [ ] **Step 4: Write failing two-route navigation tests**

```python
def test_navigator_accepts_page_already_at_destination():
    state = NavigationState(destination=True)
    result = navigator(state).reach(state.page, state.actions)
    assert result.export.control.element_id == "export"
    assert state.activations == []


def test_navigator_uses_direct_link_or_section_then_link():
    direct = NavigationState(route=("defined_reports",))
    navigator(direct).reach(direct.page, direct.actions)
    assert direct.activations == ["defined_reports"]

    nested = NavigationState(route=("section", "defined_reports"))
    navigator(nested).reach(nested.page, nested.actions)
    assert nested.activations == ["section", "defined_reports"]
```

Add failure tests for wrong origin after either click, ambiguous anchor text, and deadline exhaustion.

- [ ] **Step 5: Implement allowlisted exact-anchor discovery and condition waits**

Use two internal exact safe labels matching the validated UI. Search only visible top-document anchors, compare normalized full text, require exactly one match, and return structural identity without returning the label or other page text. `reach` checks the structural contract before navigation, after each action, and at the deadline. It sleeps only `0.1` seconds between conditions.

- [ ] **Step 6: Run focused and full tests**

Run: `python -m pytest tests/test_batch_navigation.py -q`

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add -- src/lvms_stat/batch_controls.py src/lvms_stat/batch_navigation.py tests/test_batch_navigation.py
git commit -m "feat: navigate to validated Defined Reports page"
```

---

### Task 4: Resolve and Populate the Dynamic Report Form in Stages

**Files:**
- Create: `src/lvms_stat/batch_form.py`
- Create: `tests/test_batch_form.py`
- Modify: `src/lvms_stat/batch_controls.py`

**Interfaces:**
- Consumes: `DefinedReportsPage`, `DocumentControlIdentity`, `DocumentDomActions`, `ReportJob`, expected origin, clock, sleeper.
- Produces: `discover_report_role(page, expected_origin, role) -> DocumentControlIdentity | None` and `BatchReportForm.populate(page_contract, job) -> None`.

- [ ] **Step 1: Write failing staged-role discovery tests**

```python
@pytest.mark.parametrize(
    ("role", "expected_id"),
    [
        ("category", "category"),
        ("report_id", "report-id"),
        ("analysis_codes", "analyses"),
        ("created_from", "created-from"),
        ("created_to", "created-to"),
    ],
)
def test_discovers_one_role_across_top_and_named_frames(role, expected_id):
    result = discover_report_role(FakeSafePage(role_payload(role)), EXPECTED_ORIGIN, role)
    assert result.control.element_id == expected_id
```

Add tests rejecting unknown roles, zero/multiple matches, cross-origin frames, semantic grid/treegrid controls, patient/sample/result-marked table ancestors, hidden controls, incompatible input types, and unexpected origin. Ordinary HTML layout tables remain eligible only through an exact allowlisted native/ARIA label or narrow preceding label cell. Assert that the discovery script contains none of `.value`, `.src`, `.href`, `document.cookie`, `localStorage`, or `sessionStorage`.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_batch_form.py -q`

Expected: FAIL because `batch_form.py` does not exist.

- [ ] **Step 3: Implement narrow role aliases and sanitization**

Reuse the approved Norwegian/English role aliases from `report_contract.py`, but resolve one requested role at a time across accessible documents. Use explicit native label, ARIA label, or narrow preceding label cell only. Return one `DocumentControlIdentity`; return `None` for zero/multiple matches. Never read an input's existing value.

- [ ] **Step 4: Write failing staged population test**

```python
def test_populate_advances_only_after_each_unique_control_appears():
    form = BatchReportForm(page, actions, EXPECTED_ORIGIN, clock, sleeper)
    form.populate(defined_reports_page(), job("ordered"))
    assert actions.calls == [
        ("choose", "top", "jobtypeselector", "TYPE_A"),
        ("choose", "top", "category", "CATEGORY_A"),
        ("choose", "_nav_frame1", "report-id", "REPORT-A"),
        ("replace", "_nav_frame1", "analyses", "ANALYSIS-A,ANALYSIS-B"),
        ("replace", "_nav_frame1", "created-from", "01.08.2026"),
        ("replace", "_nav_frame1", "created-to", "07.08.2026"),
    ]
```

Add tests proving that a missing/ambiguous next-stage control stops before later actions and that output/log helpers never receive `job.analysis_text()`.

- [ ] **Step 5: Implement `BatchReportForm` condition-based state machine**

Use the stable page-contract job-type control first. After each selector action, poll `discover_report_role` for the next role with a 20-second deadline and origin validation. Resolve all three parameter controls after report ID selection, then populate analysis, From, and To in that order. Do not click export in this class.

- [ ] **Step 6: Run focused and full tests**

Run: `python -m pytest tests/test_batch_form.py -q`

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add -- src/lvms_stat/batch_controls.py src/lvms_stat/batch_form.py tests/test_batch_form.py
git commit -m "feat: populate dynamic framed report form"
```

---

### Task 5: Orchestrate Three Automatic Exports in One Owned Session

**Files:**
- Create: `src/lvms_stat/batch_runner.py`
- Create: `tests/test_batch_runner.py`
- Modify: `src/lvms_stat/report_runner.py`

**Interfaces:**
- Consumes: `AppConfig`, `select_batch_jobs`, `DefinedReportsNavigator`, `BatchReportForm`, `DocumentDomActions`, `CsvArrivalDetector`, `batch_filename`, `finalize_csv`.
- Produces: `BatchRunnerDependencies` and `run_report_batch(config_path: Path, jobs_path: Path, job_keys: tuple[str, ...], *, dependencies=None, output=None, repository_root=None, timeout_seconds=600) -> int`.

- [ ] **Step 1: Write failing successful-batch orchestration test**

```python
def test_batch_runs_three_jobs_without_prompt_and_finalizes_each_csv():
    deps = BatchHarness.successful()
    output = io.StringIO()
    result = run_report_batch(
        deps.config_path,
        deps.jobs_path,
        ("ordered", "answered", "extraction"),
        dependencies=deps.dependencies(),
        output=output,
    )
    assert result == 0
    assert deps.events == [
        "navigate",
        "clear:ordered", "populate:ordered", "export:ordered", "finalize:ordered",
        "clear:answered", "populate:answered", "export:answered", "finalize:answered",
        "clear:extraction", "populate:extraction", "export:extraction", "finalize:extraction",
        "close_connection", "close_edge",
    ]
    assert "ANALYSIS-A" not in output.getvalue()
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_batch_runner.py -q`

Expected: FAIL because `batch_runner.py` does not exist.

- [ ] **Step 3: Implement injected batch dependencies and one-session orchestration**

Define defaults for config/job loaders, owned browser open, CDP connection/page factories, navigation/form/action factories, detector, finalizer, clock, and sleeper. Reuse `_close_owned` and `_open_page` by moving them from `report_runner.py` into a small internal `browser_runtime.py`, updating existing imports and tests without changing public behavior.

`run_report_batch` validates all input before opening Edge, configures the dedicated download inbox once, reaches the page once, and loops through selected jobs. For each job it revalidates the page contract, activates clear, waits for base state, populates, prints the redacted review, starts a new detector, exports, waits, requires `detected_path()`, and finalizes.

- [ ] **Step 4: Write failing stop-condition tests**

```python
@pytest.mark.parametrize(
    "failure_stage",
    ["clear", "populate", "download_ambiguous", "duplicate_target", "cleanup"],
)
def test_batch_stops_on_first_failure_without_export_retry(failure_stage):
    deps = BatchHarness.failing(failure_stage, job_key="answered")
    result = run_report_batch(
        deps.config_path,
        deps.jobs_path,
        ("ordered", "answered", "extraction"),
        dependencies=deps.dependencies(),
        output=io.StringIO(),
    )
    assert result == 2
    assert deps.export_counts["answered"] <= 1
    assert deps.export_counts["extraction"] == 0
```

Also test `KeyboardInterrupt -> 130`, invalid timeout before Edge launch, wrong job count before Edge launch, and successful earlier files remaining after a later failure.

- [ ] **Step 5: Implement fixed statuses and fail-closed cleanup**

Allowed output per job is job key, report ID, analysis count, interval, and fixed success/failure. Do not emit absolute paths. Return `0` only after three finalized files and successful cleanup, `130` for cancellation, otherwise `2`.

- [ ] **Step 6: Run focused and full tests**

Run: `python -m pytest tests/test_batch_runner.py tests/test_report_runner.py -q`

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add -- src/lvms_stat/browser_runtime.py src/lvms_stat/batch_runner.py src/lvms_stat/report_runner.py tests/test_batch_runner.py tests/test_report_runner.py
git commit -m "feat: run three automatic reports in one Edge session"
```

---

### Task 6: Expose `run-batch` and Prove the Synthetic End-to-End Flow

**Files:**
- Modify: `src/lvms_stat/__main__.py`
- Modify: `tests/test_cli.py`
- Create: `tests/fixtures/batch_defined_reports.html`
- Create: `tests/test_synthetic_batch_flow.py`
- Modify: `jobs.example.json`

**Interfaces:**
- Consumes: public `run_report_batch`.
- Produces: repeatable CLI `--job` arguments and a network-free three-report regression.

- [ ] **Step 1: Write failing CLI dispatch tests**

```python
def test_run_batch_requires_three_repeatable_job_keys_and_dispatches_in_order():
    calls = []
    result = main(
        [
            "run-batch", "--config", "config.json", "--jobs", "jobs.json",
            "--job", "ordered", "--job", "answered", "--job", "extraction",
        ],
        batch_runner=lambda config, jobs, keys: calls.append((config, jobs, keys)) or 7,
    )
    assert result == 7
    assert calls == [(Path("config.json"), Path("jobs.json"), ("ordered", "answered", "extraction"))]
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_cli.py -q`

Expected: FAIL because `run-batch` is absent.

- [ ] **Step 3: Implement the CLI command**

Add required `--config`, `--jobs`, and repeatable `--job` using `action="append"`. Convert the resulting list to a tuple at dispatch. Business validation of exact count remains in `select_batch_jobs` so direct Python Felles invocation and CLI invocation behave identically.

- [ ] **Step 4: Write the failing synthetic three-report test**

```python
def test_synthetic_batch_navigates_frames_exports_three_and_never_reads_csv(tmp_path):
    harness = SyntheticBatchHarness.from_fixture(
        Path("tests/fixtures/batch_defined_reports.html"), tmp_path.resolve()
    )
    result = run_report_batch(
        harness.config_path,
        harness.jobs_path,
        ("ordered", "answered", "extraction"),
        dependencies=harness.dependencies(),
        output=io.StringIO(),
    )
    assert result == 0
    assert harness.navigation_route == ["section", "defined_reports"]
    assert harness.export_count == 3
    assert sorted(path.name for path in harness.completed_files()) == [
        "answered__2026-08-01__2026-08-07.csv",
        "extraction__2026-08-01__2026-08-07.csv",
        "ordered__2026-08-01__2026-08-07.csv",
    ]
    assert harness.csv_open_count == 0
    assert harness.csv_read_count == 0
    assert harness.edge_closed and harness.connection_closed
```

The fixture must model the top document, `_nav_frame1`, dynamic category/report/parameter stages, clear reset, and export-created synthetic files. The harness implements semantic public interfaces, never starts Edge, and raises if production requests CSV content.

- [ ] **Step 5: Run and verify RED**

Run: `python -m pytest tests/test_synthetic_batch_flow.py -q`

Expected: FAIL until the harness and final integration seams are complete.

- [ ] **Step 6: Complete the synthetic harness and synthetic example jobs**

Update `jobs.example.json` to contain three synthetic jobs with distinct job keys/output stems and the same short interval. Keep all values synthetic. Do not add real report IDs or analysis lists.

- [ ] **Step 7: Run focused and full tests**

Run: `python -m pytest tests/test_cli.py tests/test_synthetic_batch_flow.py -q`

Run: `python -m pytest -q`

Expected: PASS without network or a real browser.

- [ ] **Step 8: Commit**

```powershell
git add -- src/lvms_stat/__main__.py tests/test_cli.py tests/fixtures/batch_defined_reports.html tests/test_synthetic_batch_flow.py jobs.example.json
git commit -m "feat: expose automatic three-report batch"
```

---

### Task 7: Document the Work-Computer Automatic Batch Gate

**Files:**
- Modify: `README.md`
- Create: `docs/work-computer-automatic-batch.md`
- Modify: `.gitignore`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `doctor`, `probe`, and `run-batch`.
- Produces: exact short-date acceptance procedure and fixed stop rules.

- [ ] **Step 1: Add a failing help/privacy contract test**

```python
def test_help_exposes_run_batch_without_real_environment_values():
    help_text = build_parser().format_help()
    assert "run-batch" in help_text
    for forbidden in ("sykehuspartner", "JSESSIONID", "PAT-DIT"):
        assert forbidden not in help_text
```

- [ ] **Step 2: Run and preserve the CLI contract**

Run: `python -m pytest tests/test_cli.py -q`

Expected: PASS after Task 6.

- [ ] **Step 3: Write the acceptance runbook**

Document this exact order:

1. pull the reviewed branch in Python Felles;
2. run `doctor` and stop unless the fixed result is ready;
3. prepare three ignored jobs with short explicit dates and distinct output stems;
4. verify all destination names are absent from the dedicated inbox;
5. invoke `run-batch` once through the tested Python entry point or the module CLI;
6. do not interact with the visible owned Edge window;
7. require three success statuses and three exact destination filenames;
8. do not open any CSV;
9. confirm owned Edge cleanup and clean Git status;
10. report only fixed category plus job key after a failure.

State explicitly that PowerGate, PyQt6, cron, backfill, CSV parsing, and Power BI are not part of this gate.

- [ ] **Step 4: Extend ignore rules only for local batch artifacts**

Ensure the dedicated download directory, local jobs/config, backups, local batch logs, `.crdownload`, CSV, and browser profiles remain ignored. Do not ignore committed synthetic fixtures.

- [ ] **Step 5: Run final verification and privacy scan**

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest -q
python -m compileall -q src tests
python -m lvms_stat --help
git diff --check
git grep -n -i -E "JSESSIONID=|LWSSO_COOKIE_KEY=|MRHSession=|Authorization:|Cookie:|sykehuspartner" -- . ':!docs/superpowers/plans/*' ':!tests/*'
git status --short
```

Expected: all tests and compilation pass; help lists `run-batch`; diff check is clean; privacy scan has zero real-environment matches; only intended documentation changes remain before commit.

- [ ] **Step 6: Commit**

```powershell
git add -- README.md docs/work-computer-automatic-batch.md .gitignore tests/test_cli.py
git commit -m "docs: add automatic batch acceptance gate"
```

---

## Final Review Gate

- [ ] Confirm the net diff does not modify Tkinter or introduce PyQt6.
- [ ] Confirm each task has a focused TDD commit and the worktree is clean.
- [ ] Run `python -m pytest -q` in a fresh process.
- [ ] Run `python -m compileall -q src tests`.
- [ ] Run `python -m lvms_stat --help` with `src` on `PYTHONPATH`.
- [ ] Review the full diff against `docs/superpowers/specs/2026-08-21-automatic-three-report-batch-design.md`.
- [ ] Run the real-environment/session-material scan and inspect only generic test assertions if any remain.
- [ ] Request a read-only code review and resolve every Critical or Important issue.
- [ ] Push the implementation branch without creating a PR unless the user explicitly requests one.
- [ ] Keep the first work-computer batch visible, automatic, limited to three jobs with short explicit dates, and stop after any failed gate.
