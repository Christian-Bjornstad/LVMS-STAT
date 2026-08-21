# LVMS CDP Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start organisation-managed Edge from `Python FELLES`, reach LVMS through SSO, discover a safe defined-report contract, and complete one supervised metadata-only CSV download.

**Architecture:** Extend the existing loopback-only Edge/CDP implementation rather than importing the larger Archer browser layer. Keep environment identifiers, report jobs, browser profiles, and downloads in ignored user-local configuration; introduce a small report-contract layer and a fail-closed supervised runner on top of the existing `BrowserPage` and `CsvArrivalDetector` boundaries.

**Tech Stack:** Python 3.11+, standard library, `websocket-client`, managed Microsoft Edge, CDP, `unittest`/`pytest`, Tkinter only where the existing app already uses it.

**Spec:** `docs/superpowers/specs/2026-08-21-lvms-cdp-integration-design.md`

## Global Constraints

- The first delivery stops after reliable browser launch, SSO navigation, safe DOM discovery, and a supervised metadata-only download test.
- CDP is bound only to `127.0.0.1` on an ephemeral port in the operating system's dynamic range.
- Edge uses a dedicated persistent profile outside the repository.
- The app starts, attaches to, and closes only the Edge process it owns.
- Navigation starts from a clean HTTPS URL with no credentials, query string, fragment, or session identifiers.
- Automation proceeds only after the configured expected origin is reached.
- No patient, sample, result, report-row, credential, cookie, session, URL-parameter, filename, or CSV content enters logs, tests, screenshots, source control, issues, or pull requests.
- Real LVMS addresses, managed-application IDs, report IDs, analysis-code lists, local paths, browser profiles, and downloads remain in ignored user-local configuration.
- Synthetic pages and placeholder identifiers are used for all committed tests and examples.
- A real CSV is detected but never opened or parsed in this subproject.
- Historical backfill, scheduling, deduplication, Excel generation, and Power BI integration are explicitly deferred.

---

## File Structure

### Existing files to modify

- `src/lvms_stat/edge.py` — make managed Edge startup retryable without weakening loopback, profile, or ownership constraints.
- `src/lvms_stat/cdp.py` — add owned download configuration and narrowly scoped DOM input primitives.
- `src/lvms_stat/config.py` — load the probe plus local integration/job configuration without exposing values.
- `src/lvms_stat/probe.py` — emit structured, sanitized capability outcomes.
- `src/lvms_stat/__main__.py` — expose `doctor`, `discover-report`, and `run-job` commands.
- `src/lvms_stat/downloads.py` — require stable completion and reject temporary or unexpected files.
- `config.example.json` — document only synthetic placeholder structure.
- `README.md` — describe the new supervised gates and privacy boundary.

### New focused modules

- `src/lvms_stat/report_job.py` — immutable report-job model, validation, review summary, and local job loader.
- `src/lvms_stat/browser_session.py` — atomically start owned Edge, wait for its CDP target, and retry transient broker handoffs.
- `src/lvms_stat/report_contract.py` — sanitized semantic mapping from LVMS report roles to stable control identities.
- `src/lvms_stat/dom_actions.py` — resolve one allowlisted control and perform click, selection, or text replacement without broad page reads.
- `src/lvms_stat/report_runner.py` — orchestrate Gate A discovery and Gate B supervised export.
- `docs/work-computer-cdp-integration.md` — exact supervised work-computer procedure and stop conditions.
- `tests/fixtures/defined_reports.html` — synthetic report form containing no real identifiers or data.

### Tests to add or extend

- `tests/test_edge.py`
- `tests/test_browser_session.py`
- `tests/test_cdp.py`
- `tests/test_config.py`
- `tests/test_probe.py`
- `tests/test_downloads.py`
- `tests/test_report_job.py`
- `tests/test_report_contract.py`
- `tests/test_dom_actions.py`
- `tests/test_report_runner.py`
- `tests/test_cli.py`
- `tests/test_synthetic_report_flow.py`

---

### Task 1: Align Managed Edge Startup and CDP Diagnostics with the Proven Pattern

**Files:**
- Modify: `src/lvms_stat/edge.py`
- Modify: `src/lvms_stat/cdp.py`
- Create: `src/lvms_stat/browser_session.py`
- Modify: `src/lvms_stat/probe.py`
- Test: `tests/test_edge.py`
- Test: `tests/test_browser_session.py`
- Test: `tests/test_probe.py`

**Interfaces:**
- Consumes: `EdgeProcess.start(profile: Path) -> EdgeProcess`, `discover_page(port: int) -> PageTarget`.
- Produces: `wait_for_page_target(port: int, *, timeout_seconds: float = 20) -> PageTarget`, `open_owned_browser(profile: Path, *, attempts: int = 3) -> OwnedBrowserStart`, and `CapabilityResult(code: CapabilityCode, ok: bool)`.

- [ ] **Step 1: Write failing Edge retry and sanitized capability tests**

```python
def test_owned_browser_retries_target_timeout_and_closes_failed_edge(tmp_path):
    first = FakeEdge(port=49152)
    second = FakeEdge(port=49153)
    edges = iter((first, second))
    waits = []

    def target_wait(port):
        waits.append(port)
        if port == 49152:
            raise CdpTimeout("stale broker")
        return PageTarget("page-2", "ws://127.0.0.1:49153/devtools/page/page-2", 49153)

    result = open_owned_browser(
        tmp_path.resolve(),
        attempts=2,
        edge_start=lambda _: next(edges),
        target_wait=target_wait,
        sleeper=lambda _: None,
    )

    assert first.closed
    assert not second.closed
    assert result.edge is second
    assert result.target.target_id == "page-2"
    assert waits == [49152, 49153]
```

```python
def test_probe_emits_fixed_capability_code_without_exception_detail():
    result = classify_probe_error(CdpTimeout("ws://127.0.0.1:55555/private"))
    assert result == CapabilityResult(CapabilityCode.CDP_UNAVAILABLE, False)
    assert "55555" not in result.user_message
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m pytest tests/test_edge.py tests/test_browser_session.py tests/test_probe.py -q`

Expected: FAIL because `open_owned_browser`, `OwnedBrowserStart`, `CapabilityResult`, `CapabilityCode`, and `classify_probe_error` do not exist.

- [ ] **Step 3: Implement bounded retry and capability classification**

Move `_wait_for_target` from `probe.py` to `cdp.py` as the public helper `wait_for_page_target`, preserving the existing bounded polling behavior. Add `--disable-session-crashed-bubble` to `build_edge_arguments` and retain `shell=False`, loopback address, ephemeral port validation, and the dedicated profile.

Add `browser_session.py`:

```python
@dataclass(frozen=True)
class OwnedBrowserStart:
    edge: EdgeProcess
    target: PageTarget


def open_owned_browser(
    profile: Path,
    *,
    attempts: int = 3,
    edge_start: Callable[[Path], EdgeProcess] = EdgeProcess.start,
    target_wait: Callable[[int], PageTarget] = wait_for_page_target,
    sleeper: Callable[[float], None] = time.sleep,
) -> OwnedBrowserStart:
    if attempts not in range(1, 4):
        raise EdgeLaunchError("Edge startup attempts are invalid")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        edge: EdgeProcess | None = None
        try:
            edge = edge_start(profile)
            return OwnedBrowserStart(edge, target_wait(edge.port))
        except (EdgeLaunchError, CdpTimeout) as exc:
            last_error = exc
            if edge is not None:
                edge.close()
            if attempt < attempts:
                sleeper(attempt * 1.5)
    raise EdgeLaunchError("managed Microsoft Edge CDP could not be started") from last_error
```

Add to `probe.py`:

```python
class CapabilityCode(StrEnum):
    READY = "ready"
    CONFIG_INVALID = "config_invalid"
    EDGE_UNAVAILABLE = "edge_unavailable"
    CDP_UNAVAILABLE = "cdp_unavailable"
    SSO_TIMEOUT = "sso_timeout"
    UNEXPECTED_ORIGIN = "unexpected_origin"
    PROTOCOL_INVALID = "protocol_invalid"
    CLEANUP_INCOMPLETE = "cleanup_incomplete"


@dataclass(frozen=True)
class CapabilityResult:
    code: CapabilityCode
    ok: bool

    @property
    def user_message(self) -> str:
        return {
            CapabilityCode.READY: "LVMS CDP capability: ready.",
            CapabilityCode.CONFIG_INVALID: "LVMS CDP capability: local configuration is invalid.",
            CapabilityCode.EDGE_UNAVAILABLE: "LVMS CDP capability: managed Edge is unavailable.",
            CapabilityCode.CDP_UNAVAILABLE: "LVMS CDP capability: local CDP is unavailable.",
            CapabilityCode.SSO_TIMEOUT: "LVMS CDP capability: SSO did not return in time.",
            CapabilityCode.UNEXPECTED_ORIGIN: "LVMS CDP capability: the expected origin was not reached.",
            CapabilityCode.PROTOCOL_INVALID: "LVMS CDP capability: Edge returned an invalid response.",
            CapabilityCode.CLEANUP_INCOMPLETE: "LVMS CDP capability: cleanup did not complete.",
        }[self.code]
```

- [ ] **Step 4: Run the focused tests**

Run: `python -m pytest tests/test_edge.py tests/test_browser_session.py tests/test_probe.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the startup and diagnostic slice**

```bash
git add -- src/lvms_stat/edge.py src/lvms_stat/cdp.py src/lvms_stat/browser_session.py src/lvms_stat/probe.py tests/test_edge.py tests/test_browser_session.py tests/test_probe.py
git commit -m "feat: add bounded LVMS CDP capability diagnostics"
```

---

### Task 2: Configure an Owned Download Inbox Through CDP

**Files:**
- Modify: `src/lvms_stat/cdp.py`
- Modify: `src/lvms_stat/downloads.py`
- Test: `tests/test_cdp.py`
- Test: `tests/test_downloads.py`

**Interfaces:**
- Consumes: `BrowserPage`, `CdpConnection.call`, `CsvArrivalDetector`.
- Produces: `BrowserPage.configure_downloads(directory: Path) -> None`, `CsvArrivalDetector(directory: Path, *, expected_suffix: str = ".csv")`.

- [ ] **Step 1: Write failing tests for download configuration and completion**

```python
def test_configure_downloads_uses_absolute_owned_directory(tmp_path):
    connection = RecordingConnection()
    page = BrowserPage(connection)
    page.configure_downloads(tmp_path.resolve())
    assert connection.calls[-1] == (
        "Browser.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": str(tmp_path.resolve())},
    )
```

```python
def test_detector_waits_while_temporary_download_exists(tmp_path):
    detector = CsvArrivalDetector(tmp_path.resolve())
    detector.start()
    (tmp_path / "report.csv.crdownload").write_bytes(b"partial")
    (tmp_path / "report.csv").write_bytes(b"partial")
    assert detector.poll() is DownloadStatus.WAITING
    (tmp_path / "report.csv.crdownload").unlink()
    assert detector.poll() is DownloadStatus.WAITING
    assert detector.poll() is DownloadStatus.DETECTED
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m pytest tests/test_cdp.py tests/test_downloads.py -q`

Expected: FAIL because download behavior and temporary-file handling are missing.

- [ ] **Step 3: Implement the narrow download boundary**

Add to `BrowserPage`:

```python
def configure_downloads(self, directory: Path) -> None:
    if not directory.is_absolute():
        raise CdpProtocolError("download directory must be absolute")
    resolved = directory.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    self._connection.call(
        "Browser.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": str(resolved)},
        timeout_seconds=5,
    )
```

Update `CsvArrivalDetector.poll` so any new `.crdownload`, `.tmp`, or `.partial` file keeps the detector in `WAITING`; more than one new completed CSV remains `AMBIGUOUS`. Do not add a method that reads file contents or exposes the path in messages.

- [ ] **Step 4: Run the focused tests**

Run: `python -m pytest tests/test_cdp.py tests/test_downloads.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the download slice**

```bash
git add -- src/lvms_stat/cdp.py src/lvms_stat/downloads.py tests/test_cdp.py tests/test_downloads.py
git commit -m "feat: add owned CDP download inbox"
```

---

### Task 3: Define and Validate Local Report Jobs

**Files:**
- Create: `src/lvms_stat/report_job.py`
- Modify: `src/lvms_stat/config.py`
- Modify: `config.example.json`
- Test: `tests/test_report_job.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: ignored local JSON and validated `AppConfig` paths.
- Produces: `ReportJob`, `ReportInterval`, `JobReview`, `load_report_jobs(path: Path) -> tuple[ReportJob, ...]`.

- [ ] **Step 1: Write failing model and privacy tests**

```python
def test_report_job_normalizes_codes_and_builds_redacted_review():
    job = validate_report_job({
        "job_key": "synthetic_ordered",
        "report_type": "TYPE_A",
        "category": "CATEGORY_A",
        "report_id": "REPORT-A",
        "analysis_codes": ["ANALYSIS-A", "ANALYSIS-B"],
        "created_from": "01.01.2026",
        "created_to": "21.08.2026",
        "output_stem": "synthetic_ordered",
    })
    assert job.analysis_codes == ("ANALYSIS-A", "ANALYSIS-B")
    assert job.review() == JobReview(
        job_key="synthetic_ordered",
        report_id="REPORT-A",
        analysis_count=2,
        created_from="01.01.2026",
        created_to="21.08.2026",
    )
    assert "ANALYSIS-A" not in str(job.review())
```

```python
@pytest.mark.parametrize("invalid", [
    {"analysis_codes": ["A", "A"]},
    {"analysis_codes": ["A,,B"]},
    {"created_from": "2026-01-01"},
    {"output_stem": "../escape"},
    {"job_key": ""},
])
def test_report_job_rejects_unsafe_or_ambiguous_values(valid_job, invalid):
    with pytest.raises(ReportJobError):
        validate_report_job({**valid_job, **invalid})
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest tests/test_report_job.py tests/test_config.py -q`

Expected: FAIL because the report-job module and integration configuration do not exist.

- [ ] **Step 3: Implement immutable job types and strict validation**

```python
@dataclass(frozen=True)
class ReportInterval:
    created_from: date
    created_to: date

    def as_lvms(self) -> tuple[str, str]:
        return (
            self.created_from.strftime("%d.%m.%Y"),
            self.created_to.strftime("%d.%m.%Y"),
        )


@dataclass(frozen=True)
class ReportJob:
    job_key: str
    report_type: str
    category: str
    report_id: str
    analysis_codes: tuple[str, ...]
    interval: ReportInterval
    output_stem: str

    def analysis_text(self) -> str:
        return ",".join(self.analysis_codes)

    def review(self) -> JobReview:
        start, end = self.interval.as_lvms()
        return JobReview(self.job_key, self.report_id, len(self.analysis_codes), start, end)
```

Use `datetime.strptime(value, "%d.%m.%Y")`, require `created_from <= created_to`, validate codes with `re.fullmatch(r"[A-Z0-9-]{1,80}", code)`, reject duplicates, cap at 500 codes, and validate job/output keys with `re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", value)`.

Extend `AppConfig` with an absolute `contract_directory` beneath local application data. Keep job values in a separate ignored file passed to `load_report_jobs`; do not add real jobs to `config.example.json`.

- [ ] **Step 4: Add a synthetic-only example**

Add this shape to `config.example.json`:

```json
{
  "landing_url": "https://lvms.example.invalid/",
  "profile_directory": "C:/Users/example/AppData/Local/LVMS-STAT/edge-profile",
  "download_directory": "C:/Approved/LVMS-STAT/inbox",
  "workflow_directory": "C:/Users/example/AppData/Local/LVMS-STAT/workflows",
  "contract_directory": "C:/Users/example/AppData/Local/LVMS-STAT/contracts"
}
```

- [ ] **Step 5: Run focused and full tests**

Run: `python -m pytest tests/test_report_job.py tests/test_config.py -q`

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 6: Commit the job-model slice**

```bash
git add -- src/lvms_stat/report_job.py src/lvms_stat/config.py config.example.json tests/test_report_job.py tests/test_config.py
git commit -m "feat: add privacy-safe local report jobs"
```

---

### Task 4: Discover and Store a Sanitized Defined-Report Contract

**Files:**
- Create: `src/lvms_stat/report_contract.py`
- Modify: `src/lvms_stat/inspection.py`
- Test: `tests/test_report_contract.py`
- Test: `tests/test_inspection.py`
- Create: `tests/fixtures/defined_reports.html`

**Interfaces:**
- Consumes: `BrowserPage.evaluate_safe`, `ControlIdentity`, expected origin, local contract directory.
- Produces: `ReportContract`, `discover_report_contract(page, expected_origin) -> ReportContract`, `save_contract(contract, directory) -> Path`, `load_contract(path) -> ReportContract`.

- [ ] **Step 1: Create the synthetic fixture**

```html
<!doctype html>
<html lang="en">
  <body>
    <label for="report-type">Report type</label>
    <select id="report-type"><option>TYPE_A</option></select>
    <label for="category">Category</label>
    <select id="category"><option>CATEGORY_A</option></select>
    <label for="report-id">Report id</label>
    <select id="report-id"><option>REPORT-A</option></select>
    <section id="parameters">
      <label for="analyses">Analyses</label><input id="analyses">
      <label for="created-from">Created from</label><input id="created-from">
      <label for="created-to">Created to</label><input id="created-to">
    </section>
    <button id="export">Export</button>
  </body>
</html>
```

- [ ] **Step 2: Write failing contract discovery tests**

```python
def test_contract_requires_exactly_one_control_for_every_role():
    raw = synthetic_contract_payload()
    contract = sanitize_report_contract(raw)
    assert contract.report_type.element_id == "report-type"
    assert contract.export.tag == "BUTTON"


def test_contract_rejects_values_urls_and_patient_containers():
    raw = synthetic_contract_payload()
    raw["analysis_codes"]["value"] = "SECRET"
    with pytest.raises(ReportContractError):
        sanitize_report_contract(raw)
```

```python
def test_contract_file_uses_opaque_name_and_contains_no_values(tmp_path):
    path = save_contract(synthetic_contract(), tmp_path.resolve())
    assert path.parent == tmp_path.resolve()
    assert path.name.endswith(".json")
    text = path.read_text(encoding="utf-8")
    assert "value" not in text.casefold()
    assert "REPORT-A" not in text
```

- [ ] **Step 3: Run tests and verify they fail**

Run: `python -m pytest tests/test_report_contract.py tests/test_inspection.py -q`

Expected: FAIL because contract discovery and storage are not implemented.

- [ ] **Step 4: Implement a fixed seven-role contract**

```python
@dataclass(frozen=True)
class ReportContract:
    report_type: ControlIdentity
    category: ControlIdentity
    report_id: ControlIdentity
    analysis_codes: ControlIdentity
    created_from: ControlIdentity
    created_to: ControlIdentity
    export: ControlIdentity
```

The injected discovery script may read label text and fixed control attributes only. It returns an object whose exact keys are:

```python
CONTRACT_ROLES = frozenset({
    "report_type", "category", "report_id", "analysis_codes",
    "created_from", "created_to", "export",
})
```

Reuse the existing exclusion selectors for tables/grids and patient-, sample-, and result-like containers. Reject unknown keys, duplicate controls, empty locators, more than one candidate per role, any value-bearing key, and contracts discovered outside `expected_origin`.

Store with `secrets.token_hex(16) + ".json"`; never derive the filename from report text, user text, URLs, or control labels.

- [ ] **Step 5: Run the focused tests**

Run: `python -m pytest tests/test_report_contract.py tests/test_inspection.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the contract slice**

```bash
git add -- src/lvms_stat/report_contract.py src/lvms_stat/inspection.py tests/test_report_contract.py tests/test_inspection.py tests/fixtures/defined_reports.html
git commit -m "feat: discover sanitized LVMS report contracts"
```

---

### Task 5: Add Fail-Closed DOM Actions for Allowlisted Controls

**Files:**
- Create: `src/lvms_stat/dom_actions.py`
- Modify: `src/lvms_stat/cdp.py`
- Test: `tests/test_dom_actions.py`
- Test: `tests/test_cdp.py`

**Interfaces:**
- Consumes: `BrowserPage`, `ControlIdentity`, `ReportContract`, expected origin.
- Produces: `DomActions.activate(control)`, `DomActions.replace_text(control, text)`, `DomActions.choose_text(control, text)`, `BrowserPage.insert_text(text)`, `BrowserPage.press_key(key)`.

- [ ] **Step 1: Write failing action-boundary tests**

```python
def test_replace_text_resolves_one_control_and_never_reads_existing_value():
    page = RecordingPage(resolve_count=1)
    actions = DomActions(page, "https://lvms.example.invalid")
    actions.replace_text(ControlIdentity("INPUT", element_id="analyses"), "ANALYSIS-A")
    assert page.operations == [
        ("origin", "https://lvms.example.invalid"),
        ("focus", "analyses"),
        ("replace", "ANALYSIS-A"),
    ]
    assert all("read_value" not in operation for operation in page.operations)
```

```python
@pytest.mark.parametrize("count", [0, 2])
def test_action_fails_when_control_is_not_unique(count):
    actions = DomActions(RecordingPage(resolve_count=count), "https://lvms.example.invalid")
    with pytest.raises(DomActionError):
        actions.activate(ControlIdentity("BUTTON", element_id="export"))
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest tests/test_dom_actions.py tests/test_cdp.py -q`

Expected: FAIL because the action layer and CDP input helpers do not exist.

- [ ] **Step 3: Implement identity-based action resolution**

```python
class DomActions:
    def __init__(self, page: BrowserPage, expected_origin: str) -> None:
        self._page = page
        self._expected_origin = expected_origin

    def _resolve(self, control: ControlIdentity) -> str:
        if self._page.current_origin() != self._expected_origin:
            raise UnexpectedOriginError("Edge reached an unexpected origin")
        token = self._page.resolve_control(control)
        if not token:
            raise DomActionError("report control is not uniquely available")
        return token

    def activate(self, control: ControlIdentity) -> None:
        self._page.activate_control(self._resolve(control))

    def replace_text(self, control: ControlIdentity, text: str) -> None:
        token = self._resolve(control)
        self._page.focus_control(token)
        self._page.replace_focused_text(text)
```

`resolve_control` must prefer exact `id`, then exact `name`, then the full recorded locator. It returns an opaque per-call token, not HTML. The browser-side script must require exactly one visible, enabled control of the expected tag/type and reject controls under the existing excluded containers.

`choose_text` uses native `SELECT` option matching when available. For a custom editable selector, it focuses the control, replaces text, dispatches `input` and `change`, then uses CDP `Input.dispatchKeyEvent` for `Enter`. Only the expected configuration text supplied by `ReportJob` may be entered.

- [ ] **Step 4: Add strict CDP text and key helpers**

```python
def insert_text(self, text: str) -> None:
    if not isinstance(text, str) or not 1 <= len(text) <= 40_000:
        raise CdpProtocolError("text input is invalid")
    self._connection.call("Input.insertText", {"text": text}, timeout_seconds=5)


def press_key(self, key: str) -> None:
    allowed = {"Enter": 13, "Tab": 9}
    if key not in allowed:
        raise CdpProtocolError("key input is invalid")
    code = allowed[key]
    self._connection.call(
        "Input.dispatchKeyEvent",
        {"type": "keyDown", "key": key, "windowsVirtualKeyCode": code},
        timeout_seconds=2,
    )
    self._connection.call(
        "Input.dispatchKeyEvent",
        {"type": "keyUp", "key": key, "windowsVirtualKeyCode": code},
        timeout_seconds=2,
    )
```

- [ ] **Step 5: Run focused and full tests**

Run: `python -m pytest tests/test_dom_actions.py tests/test_cdp.py -q`

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 6: Commit the action slice**

```bash
git add -- src/lvms_stat/dom_actions.py src/lvms_stat/cdp.py tests/test_dom_actions.py tests/test_cdp.py
git commit -m "feat: add allowlisted LVMS DOM actions"
```

---

### Task 6: Build the Supervised Gate A and Gate B Runner

**Files:**
- Create: `src/lvms_stat/report_runner.py`
- Modify: `src/lvms_stat/__main__.py`
- Modify: `src/lvms_stat/probe.py`
- Test: `tests/test_report_runner.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `AppConfig`, `ReportJob`, `ReportContract`, `DomActions`, `BrowserPage`, `CsvArrivalDetector`.
- Produces: `discover_report(config_path: Path) -> int`, `run_report_job(config_path: Path, jobs_path: Path, contract_path: Path, job_key: str) -> int`.

- [ ] **Step 1: Write failing Gate A and Gate B orchestration tests**

```python
def test_gate_a_discovers_contract_and_stops_without_export(dependencies, tmp_path):
    result = discover_report(
        dependencies.config_path,
        dependencies=dependencies.with_contract(synthetic_contract()),
        output=io.StringIO(),
        input_func=lambda _: "DISCOVER",
    )
    assert result == 0
    assert dependencies.actions.export_calls == 0
    assert dependencies.contract_store.saved == 1
```

```python
def test_gate_b_requires_exact_export_confirmation(dependencies):
    output = io.StringIO()
    result = run_report_job(
        dependencies.config_path,
        dependencies.jobs_path,
        dependencies.contract_path,
        "synthetic_ordered",
        dependencies=dependencies,
        output=output,
        input_func=lambda _: "yes",
    )
    assert result == 130
    assert dependencies.actions.export_calls == 0
    assert "ANALYSIS-A" not in output.getvalue()
```

```python
def test_gate_b_populates_allowlisted_fields_and_detects_one_csv(dependencies):
    result = run_report_job(
        dependencies.config_path,
        dependencies.jobs_path,
        dependencies.contract_path,
        "synthetic_ordered",
        dependencies=dependencies,
        output=io.StringIO(),
        input_func=lambda _: "EXPORT",
    )
    assert result == 0
    assert dependencies.actions.calls == [
        ("choose", "report_type", "TYPE_A"),
        ("choose", "category", "CATEGORY_A"),
        ("choose", "report_id", "REPORT-A"),
        ("replace", "analysis_codes", "ANALYSIS-A,ANALYSIS-B"),
        ("replace", "created_from", "01.01.2026"),
        ("replace", "created_to", "21.08.2026"),
        ("activate", "export"),
    ]
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest tests/test_report_runner.py tests/test_cli.py -q`

Expected: FAIL because the runner and new CLI commands do not exist.

- [ ] **Step 3: Implement an injected, testable runner**

```python
@dataclass(frozen=True)
class RunnerDependencies:
    browser_open: Callable[[Path], OwnedBrowserStart] = open_owned_browser
    connection_open: Callable[[PageTarget], Any] = CdpConnection.open
    page_factory: Callable[[Any], BrowserPage] = BrowserPage
    detector_factory: Callable[[Path], CsvArrivalDetector] = CsvArrivalDetector
    sleeper: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
```

The runner sequence is exact:

```python
actions.choose_text(contract.report_type, job.report_type)
actions.choose_text(contract.category, job.category)
actions.choose_text(contract.report_id, job.report_id)
actions.replace_text(contract.analysis_codes, job.analysis_text())
created_from, created_to = job.interval.as_lvms()
actions.replace_text(contract.created_from, created_from)
actions.replace_text(contract.created_to, created_to)
```

After each selector action, wait for the next contract control to become uniquely available rather than sleeping a fixed number of seconds. Before export, print only `JobReview` fields and require exact `EXPORT`. Configure the CDP download inbox and start `CsvArrivalDetector` before activating `contract.export`. Poll for at most the configured report timeout, default 600 seconds. Success output is exactly `Report download: one completed CSV detected.\n`.

All cleanup follows `run_probe`: close connection, then close only owned Edge; cleanup failure changes the exit code to `2`.

- [ ] **Step 4: Add CLI commands**

```text
python -m lvms_stat doctor --config config.json
python -m lvms_stat discover-report --config config.json
python -m lvms_stat run-job --config config.json --jobs jobs.json --contract <opaque>.json --job synthetic_ordered
```

`doctor` replaces no existing command; keep `probe`, `inspect`, and `app` for compatibility. CLI help must state that real job and contract files are local-only and ignored.

- [ ] **Step 5: Run focused and full tests**

Run: `python -m pytest tests/test_report_runner.py tests/test_cli.py -q`

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 6: Commit the supervised runner slice**

```bash
git add -- src/lvms_stat/report_runner.py src/lvms_stat/__main__.py src/lvms_stat/probe.py tests/test_report_runner.py tests/test_cli.py
git commit -m "feat: add supervised LVMS report gates"
```

---

### Task 7: Add a Synthetic End-to-End Report Flow

**Files:**
- Create: `tests/test_synthetic_report_flow.py`
- Modify: `tests/fixtures/defined_reports.html`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: the public Gate A/Gate B runner interfaces from Task 6.
- Produces: a deterministic synthetic regression that covers contract discovery, field population, export confirmation, fake CSV completion, and cleanup.

- [ ] **Step 1: Write the failing synthetic flow test**

```python
def test_synthetic_defined_report_flow_never_opens_or_reads_csv(tmp_path):
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
        input_func=lambda _: "EXPORT",
    )
    assert result == 0
    assert harness.csv_open_count == 0
    assert harness.csv_read_count == 0
    assert harness.edge_closed
    assert harness.connection_closed
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m pytest tests/test_synthetic_report_flow.py -q`

Expected: FAIL because `SyntheticReportHarness` has not been implemented in the test module.

- [ ] **Step 3: Implement the in-process synthetic harness**

The harness is test-only. It provides a fake `BrowserPage` backed by the committed HTML fixture, records semantic operations, creates `synthetic.csv` only when the export control is activated, and raises immediately if any production code asks to open or read that file. It must not launch Edge or use network access in the default test suite.

Register markers in `pyproject.toml` only if an optional real-Edge smoke test is added:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
markers = ["edge_smoke: requires installed managed Edge and runs only when explicitly selected"]
```

- [ ] **Step 4: Run the synthetic and full suites**

Run: `python -m pytest tests/test_synthetic_report_flow.py -q`

Run: `python -m pytest -q`

Expected: PASS with no network or real browser access.

- [ ] **Step 5: Commit the synthetic integration slice**

```bash
git add -- tests/test_synthetic_report_flow.py tests/fixtures/defined_reports.html pyproject.toml
git commit -m "test: cover synthetic LVMS report flow"
```

---

### Task 8: Document and Verify the Work-Computer Gates

**Files:**
- Create: `docs/work-computer-cdp-integration.md`
- Modify: `README.md`
- Modify: `.gitignore`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `doctor`, `discover-report`, and `run-job` commands.
- Produces: exact supervised test instructions, expected fixed messages, stop conditions, and privacy checks.

- [ ] **Step 1: Write a failing documentation/CLI contract test**

```python
def test_help_exposes_supervised_gates_without_real_environment_values():
    parser = build_parser()
    help_text = parser.format_help()
    assert "doctor" in help_text
    assert "discover-report" in help_text
    assert "run-job" in help_text
    for forbidden in ("internal.example", "REAL_APP_ID", "JSESSIONID"):
        assert forbidden not in help_text
```

- [ ] **Step 2: Run the CLI test**

Run: `python -m pytest tests/test_cli.py -q`

Expected: PASS after Task 6; preserve it while adding documentation.

- [ ] **Step 3: Write the work-computer runbook**

The runbook must contain these ordered gates:

```text
Gate 0 — start LVMS-STAT manually in Python FELLES
Gate 1 — run doctor; stop unless the fixed result is ready
Gate 2 — run discover-report on the defined-report page without patient/sample tables
Gate 3 — review the local opaque contract file; do not copy it to GitHub
Gate 4 — run one configured job and review job key, report ID, analysis count, and dates
Gate 5 — type EXPORT once; stop if origin, selector, file count, or cleanup checks fail
Gate 6 — confirm one local CSV exists; do not open it during this subproject
```

Include a troubleshooting table mapping each `CapabilityCode` to one action. Do not instruct users to change Edge policy, registry, security settings, or authentication material.

- [ ] **Step 4: Extend `.gitignore` and README**

Ensure these patterns are ignored:

```gitignore
config.json
jobs.json
contracts/
data/
downloads/
browser_profiles/
*.crdownload
```

README must say that Archer-prosess proves direct managed Edge CDP in the approved Python environment, while LVMS-specific SSO and selectors still require the supervised gates.

- [ ] **Step 5: Run final verification**

Run: `python -m pytest -q`

Run: `python -m compileall -q src tests`

Run: `python -m lvms_stat --help`

Run: `git diff --check`

Run a repository scan and require zero matches for real environment identifiers, session material, and patient data:

```powershell
rg -n -i "JSESSIONID|LWSSO_COOKIE|MRHSession|traceparent|cookie:|authorization:|patient.?id" .
```

Inspect any match manually; synthetic assertions mentioning a forbidden word are acceptable only when they prove redaction, while real values are never acceptable.

- [ ] **Step 6: Commit the runbook**

```bash
git add -- .gitignore README.md docs/work-computer-cdp-integration.md tests/test_cli.py
git commit -m "docs: add supervised LVMS CDP runbook"
```

---

## Final Review Gate

- [ ] Confirm every task commit is atomic and `git status --short` is clean.
- [ ] Run `python -m pytest -q` from a fresh process.
- [ ] Run `python -m compileall -q src tests`.
- [ ] Run `python -m lvms_stat --help`.
- [ ] Review the full diff against `docs/superpowers/specs/2026-08-21-lvms-cdp-integration-design.md`.
- [ ] Perform the secret/internal-identifier scan and record only the number of matches after synthetic-test exclusions.
- [ ] Request code review before pushing the implementation branch or changing the existing draft PR.
- [ ] Keep the first real work-computer run supervised; do not proceed from Gate A to Gate B after any origin, selector, cleanup, or privacy failure.
