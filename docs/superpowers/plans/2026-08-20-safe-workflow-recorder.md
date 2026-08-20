# Safe Workflow Recorder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Tkinter application that automatically records one sanitized LVMS Defined Reports workflow, reviews parameter roles, detects the resulting CSV without reading it, and can ask Windows to open it locally.

**Architecture:** The existing visible Edge/CDP boundary remains responsible for browser launch, navigation, and origin enforcement. A page-local allowlisted event queue is drained by a Python polling recorder; an application controller coordinates it with a filesystem-metadata-only CSV detector, versioned workflow storage, and a thin Tkinter view through injected interfaces that are testable without a display.

**Tech Stack:** Python 3.11+, Tkinter/ttk standard library, pathlib/json/threading/queue standard library, existing `websocket-client>=1.8,<2`, and `unittest` synthetic tests.

**Spec:** `docs/superpowers/specs/2026-08-20-safe-workflow-recorder-design.md`

## Global Constraints

- Run only on the organisation-controlled work computer with the user's normal authorised LVMS access.
- Keep Python at `>=3.11` and add no runtime dependency beyond existing `websocket-client>=1.8,<2`.
- Launch visible managed Edge with a dedicated profile beneath Local AppData and loopback-only ephemeral CDP.
- Accept recorded events only on the configured HTTPS LVMS origin; allow SSO navigation but never record SSO actions.
- Never read or persist typed values, keystrokes, patient/report contents, page tables, cookies, storage, network requests, response bodies, download URLs, filenames, or screenshots.
- CSV detection may use only bounded filesystem metadata; local opening must not read file bytes.
- Persist sanitized workflow JSON only beneath Local AppData and outside the repository, after an explicit save.
- Tests use synthetic identifiers and temporary files only; they never launch Edge, contact LVMS, or open a real CSV.
- Version 1 records and reviews one workflow; replay, relative dates, multiple workflows, report parsing, scheduling, and Power BI output are excluded.

## File Structure

- Modify `src/lvms_stat/config.py`: validate app download and workflow-storage paths alongside the existing Edge settings.
- Modify `config.example.json`: show safe local path placeholders only.
- Create `src/lvms_stat/workflow.py`: immutable step/workflow models, parameter roles, and recorder states.
- Create `src/lvms_stat/workflow_store.py`: strict versioned JSON serialization and atomic local save/load.
- Create `src/lvms_stat/recorder_events.py`: fixed browser listener script and double-sided event sanitization.
- Create `src/lvms_stat/recorder.py`: approved-origin listener installation, nonce enforcement, and bounded queue polling.
- Create `src/lvms_stat/downloads.py`: metadata-only CSV arrival detection and injected local-open boundary.
- Create `src/lvms_stat/recording_service.py`: background supervised Edge recording lifecycle and safe service events.
- Create `src/lvms_stat/app_controller.py`: UI-independent state transitions and commands.
- Create `src/lvms_stat/tk_app.py`: thin Tkinter/ttk rendering and main-thread event polling.
- Modify `src/lvms_stat/__main__.py`: add the `app` command without changing `probe` or `inspect` behavior.
- Modify `README.md` and create `docs/work-computer-recorder.md`: local setup, privacy boundary, and supervised validation.
- Create focused `tests/test_*.py` files mirroring every new module.

---

### Task 1: Recorder Configuration Boundary

**Files:**
- Modify: `src/lvms_stat/config.py`
- Modify: `config.example.json`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: existing `load_config(path, repository_root, allowed_profile_root)` and `ProbeConfig`.
- Produces: `AppConfig(landing_url: str, expected_origin: str, profile_directory: Path, download_directory: Path, workflow_directory: Path)` and `load_app_config(...) -> AppConfig`.

- [ ] **Step 1: Write failing configuration tests**

Add tests that construct temporary `repository`, `local-app-data`, and `downloads` directories and assert:

```python
config = validate_app_config(
    {
        "landing_url": "https://lvms.example.invalid/",
        "profile_directory": str(local_app_data / "LVMS-STAT" / "edge-profile"),
        "download_directory": str(downloads),
        "workflow_directory": str(local_app_data / "LVMS-STAT" / "workflows"),
    },
    repository_root=repository,
    allowed_local_root=local_app_data,
)
self.assertEqual(config.download_directory, downloads.resolve())
self.assertEqual(
    config.workflow_directory,
    (local_app_data / "LVMS-STAT" / "workflows").resolve(),
)
```

Add rejection cases for relative download paths, either app path inside the repository, workflow storage outside Local AppData, and workflow storage equal to the Local AppData root.

- [ ] **Step 2: Run the tests to verify RED**

Run: `python -m unittest tests.test_config -v`

Expected: import failure for `validate_app_config` and `AppConfig`.

- [ ] **Step 3: Implement strict app configuration**

Add:

```python
@dataclass(frozen=True)
class AppConfig(ProbeConfig):
    download_directory: Path
    workflow_directory: Path


def validate_app_config(
    raw: Mapping[str, object],
    *,
    repository_root: Path,
    allowed_local_root: Path | None = None,
) -> AppConfig:
    local_root = _resolve_local_root(allowed_local_root)
    probe = validate_config(
        raw,
        repository_root=repository_root,
        allowed_profile_root=local_root,
    )
    download_directory = _absolute_external_directory(
        raw, "download_directory", repository_root
    )
    workflow_directory = _absolute_external_directory(
        raw, "workflow_directory", repository_root
    )
    if workflow_directory == local_root or local_root not in workflow_directory.parents:
        raise ConfigError("workflow_directory must be beneath local application data")
    return AppConfig(
        landing_url=probe.landing_url,
        expected_origin=probe.expected_origin,
        profile_directory=probe.profile_directory,
        download_directory=download_directory,
        workflow_directory=workflow_directory,
    )
```

Factor `_resolve_local_root` and `_absolute_external_directory` so all containment checks use resolved absolute `Path` objects. Implement `load_app_config` with the same sanitized JSON error behavior as `load_config`. Update `config.example.json` with `.invalid` and `%LOCALAPPDATA%`-style documentation values, never a real internal host or username.

- [ ] **Step 4: Run focused and full tests**

Run:

```powershell
python -m unittest tests.test_config -v
python -m unittest discover -s tests -t . -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit the configuration increment**

```powershell
git add -- src/lvms_stat/config.py config.example.json tests/test_config.py
git commit -m "feat: validate recorder application paths"
```

### Task 2: Workflow Model and State Machine

**Files:**
- Create: `src/lvms_stat/workflow.py`
- Test: `tests/test_workflow.py`

**Interfaces:**
- Consumes: no browser or UI code.
- Produces: `RecorderState`, `StepKind`, `ParameterRole`, `ControlIdentity`, `WorkflowStep`, `WorkflowDraft`, `validate_workflow(draft) -> WorkflowDraft`, `transition(state, command) -> RecorderState`, and `assign_parameter_role(draft, step_id, role) -> WorkflowDraft`.

- [ ] **Step 1: Write failing model tests**

Cover valid transitions and reject invalid ones:

```python
self.assertEqual(transition(RecorderState.READY, "start"), RecorderState.STARTING)
self.assertEqual(transition(RecorderState.STARTING, "connected"), RecorderState.RECORDING)
self.assertEqual(transition(RecorderState.RECORDING, "stop"), RecorderState.STOPPED)
with self.assertRaises(WorkflowError):
    transition(RecorderState.READY, "download_detected")
```

Create an edited-field step, assign `ParameterRole.FROM_DATE`, and assert the immutable replacement contains the role but no value field. Verify non-field steps reject parameter roles and names/notes enforce bounded lengths.

- [ ] **Step 2: Run the tests to verify RED**

Run: `python -m unittest tests.test_workflow -v`

Expected: module import failure.

- [ ] **Step 3: Implement minimal immutable models**

Use string enums and frozen dataclasses:

```python
class RecorderState(StrEnum):
    READY = "ready"
    STARTING = "starting"
    RECORDING = "recording"
    STOPPED = "stopped"
    DOWNLOAD_DETECTED = "download_detected"
    ERROR = "error"


class StepKind(StrEnum):
    ACTIVATE = "activate"
    SELECT = "select"
    FIELD_EDITED = "field_edited"


class ParameterRole(StrEnum):
    FROM_DATE = "from_date"
    TO_DATE = "to_date"
    OTHER_PARAMETER = "other_parameter"


@dataclass(frozen=True)
class ControlIdentity:
    tag: str
    control_type: str = ""
    element_id: str = ""
    name: str = ""
    role: str = ""
    label: str = ""
    locator: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowStep:
    step_id: int
    kind: StepKind
    control: ControlIdentity
    parameter_role: ParameterRole | None = None


@dataclass(frozen=True)
class WorkflowDraft:
    name: str
    notes: str
    steps: tuple[WorkflowStep, ...] = ()
    download_detected: bool = False
```

Define a closed transition mapping for READY/start, STARTING/connected, STARTING/fail, RECORDING/stop, RECORDING/download_detected, RECORDING/fail, STOPPED/download_detected, and every active state/close. Limit a stripped workflow name to 80 characters and notes to 500 characters. `WorkflowDraft` must not define a generic metadata dictionary or any value/path/URL fields.

- [ ] **Step 4: Run focused and full tests**

Run both the focused test module and the full discovery command. Expected: all pass.

- [ ] **Step 5: Commit the domain increment**

```powershell
git add -- src/lvms_stat/workflow.py tests/test_workflow.py
git commit -m "feat: model safe recorder workflow state"
```

### Task 3: Versioned Local Workflow Storage

**Files:**
- Create: `src/lvms_stat/workflow_store.py`
- Test: `tests/test_workflow_store.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `WorkflowDraft`, `WorkflowStep`, and enum/model validators from Task 2.
- Produces: `WorkflowStore(root: Path)`, `save(draft: WorkflowDraft) -> Path`, and `load(path: Path) -> WorkflowDraft`.

- [ ] **Step 1: Write failing storage tests**

Use `TemporaryDirectory` to verify a save/load round trip, explicit rejection of unknown keys and schema versions, and absence of forbidden serialized keys:

```python
saved = WorkflowStore(root).save(draft)
payload = saved.read_text(encoding="utf-8")
self.assertNotRegex(
    payload.lower(),
    r'"(value|url|path|filename|cookie|token|authorization)"\s*:',
)
self.assertEqual(WorkflowStore(root).load(saved), draft)
```

Patch `Path.replace` to fail and assert no partially named final JSON exists. Assert the root must be absolute and the generated filename is an opaque UUID rather than the workflow name.

- [ ] **Step 2: Run the tests to verify RED**

Run: `python -m unittest tests.test_workflow_store -v`

Expected: module import failure.

- [ ] **Step 3: Implement strict serialization and atomic replacement**

Use schema version `1`, exact-key validation at every object level, `tempfile.NamedTemporaryFile(delete=False, dir=root)`, `flush`, `os.fsync`, and `Path.replace`. The public save flow is:

```python
def save(self, draft: WorkflowDraft) -> Path:
    safe = validate_workflow(draft)
    payload = {"schema_version": 1, **workflow_to_json(safe)}
    destination = self._root / f"{uuid.uuid4().hex}.json"
    _atomic_json_write(destination, payload)
    return destination
```

Do not serialize origin, timestamps from LVMS, file information, or exception details. Add defensive ignore patterns `workflows/` and `*.workflow.json`.

- [ ] **Step 4: Run focused/full tests and scan the fixture output**

Run the focused and full suites. Expected: all pass and temporary JSON contains only schema, name, notes, steps, parameter roles, and completion flag.

- [ ] **Step 5: Commit storage**

```powershell
git add -- .gitignore src/lvms_stat/workflow_store.py tests/test_workflow_store.py
git commit -m "feat: store sanitized workflows atomically"
```

### Task 4: Browser Event Allowlist and Sanitizer

**Files:**
- Create: `src/lvms_stat/recorder_events.py`
- Test: `tests/test_recorder_events.py`

**Interfaces:**
- Consumes: `ControlIdentity`, `StepKind`, and `WorkflowStep` from Task 2.
- Produces: `RECORDER_INSTALL_SCRIPT_TEMPLATE`, `RECORDER_DRAIN_SCRIPT_TEMPLATE`, `RecorderEventError`, and `sanitize_event_batch(raw: object, *, start_step_id: int, expected_nonce: str) -> tuple[WorkflowStep, ...]`.

- [ ] **Step 1: Write failing sanitizer and script tests**

Assert a minimal activation candidate becomes a step. Add rejections for unknown keys, wrong nonce, invalid kind/tag, password/hidden types, more than 100 events, locator depth over 12, and any nested forbidden key. Assert strings longer than 120 characters are truncated to exactly 120 before a step is created.

Inspect the fixed JavaScript source as text and assert it does not access:

```python
for forbidden in (
    ".value", "document.cookie", "localStorage", "sessionStorage",
    "clipboardData", "innerHTML", "outerHTML", "performance.getEntries",
):
    self.assertNotIn(forbidden, RECORDER_INSTALL_SCRIPT_TEMPLATE)
```

Assert the script excludes `table`, `[role='grid']`, `[role='treegrid']`, password/hidden controls, and content-editable regions before queueing.

- [ ] **Step 2: Run the tests to verify RED**

Run: `python -m unittest tests.test_recorder_events -v`

Expected: module import failure.

- [ ] **Step 3: Implement fixed listener scripts and strict Python sanitizer**

The installed page object must expose only an internal bounded queue and nonce. Install the same fixed handlers recursively in accessible same-origin frames; skip cross-origin frames without reading their attributes or content. Event handlers map `click`, safe `change`, and safe `blur` into `activate`, `select`, and `field_edited`. The browser candidate schema is exactly:

```python
EVENT_FIELDS = frozenset({"nonce", "kind", "control"})
CONTROL_FIELDS = frozenset(
    {"tag", "type", "id", "name", "role", "label", "locator"}
)
FORBIDDEN_FIELDS = frozenset(
    {"value", "href", "src", "url", "cookie", "token", "authorization",
     "textcontent", "innertext", "filename", "path"}
)
```

Reject an entire batch if any mapping contains a forbidden or unknown field. Limit a batch to 100 candidates, each string to 120 characters, and locator depth to 12. Drop excluded control kinds. Construct sequential `WorkflowStep` objects only after full-batch validation succeeds.

- [ ] **Step 4: Run focused/full tests and source scans**

Run the focused/full suites plus:

```powershell
rg -n "\.value|document\.cookie|localStorage|sessionStorage|clipboardData|innerHTML|outerHTML" src/lvms_stat/recorder_events.py
```

Expected: tests pass; matches occur only in Python denial lists or test assertions, never in executable JavaScript property reads.

- [ ] **Step 5: Commit the event boundary**

```powershell
git add -- src/lvms_stat/recorder_events.py tests/test_recorder_events.py
git commit -m "feat: sanitize automatic browser actions"
```

### Task 5: Approved-Origin Polling Recorder

**Files:**
- Create: `src/lvms_stat/recorder.py`
- Modify: `src/lvms_stat/cdp.py`
- Test: `tests/test_recorder.py`
- Test: `tests/test_cdp.py`

**Interfaces:**
- Consumes: `BrowserPage`, fixed scripts, and `sanitize_event_batch`.
- Produces: `BrowserPage.evaluate_safe(expression, timeout_seconds) -> object`, `RecorderSession(page, expected_origin, nonce_factory)`, `install() -> None`, and `poll() -> tuple[WorkflowStep, ...]`.

- [ ] **Step 1: Write failing recorder lifecycle tests**

Use a fake page recording evaluation expressions and returning synthetic origin/readiness/batches. Verify:

```python
session = RecorderSession(
    page=fake_page,
    expected_origin="https://lvms.example.invalid",
    nonce_factory=lambda: "synthetic-nonce",
)
session.install()
self.assertEqual(session.poll()[0].step_id, 1)
self.assertNotIn("synthetic-nonce", repr(session))
```

Assert `poll` rechecks origin before draining, a changed document marker causes safe reinstall with the same session nonce, late/wrong-nonce events fail closed, and raw evaluation errors are converted to `RecorderUnavailable` without payload text.

- [ ] **Step 2: Run the tests to verify RED**

Run: `python -m unittest tests.test_recorder tests.test_cdp -v`

Expected: missing recorder module or `evaluate_safe`.

- [ ] **Step 3: Add the narrow CDP evaluation seam and recorder**

Expose only the existing bounded evaluator:

```python
def evaluate_safe(self, expression: str, *, timeout_seconds: float = 2) -> object:
    return self._evaluate(expression, timeout_seconds=timeout_seconds)

def current_origin(self) -> str:
    origin = self._evaluate("location.origin", timeout_seconds=2)
    if not isinstance(origin, str):
        raise CdpProtocolError("Edge returned an invalid origin")
    return origin
```

`RecorderSession.install` verifies `current_origin()`, creates a random nonce with `secrets.token_urlsafe(24)`, installs the fixed listener in the top document and accessible same-origin frames, and records a non-sensitive document marker. `poll` verifies origin, evaluates the drain script, sanitizes the batch, increments the next step ID, and never exposes raw payloads in exceptions or representations.

- [ ] **Step 4: Run focused/full tests**

Run the focused and full suites. Expected: all pass, including existing origin and control-inspection tests.

- [ ] **Step 5: Commit the recorder boundary**

```powershell
git add -- src/lvms_stat/cdp.py src/lvms_stat/recorder.py tests/test_cdp.py tests/test_recorder.py
git commit -m "feat: poll safe LVMS workflow actions"
```

### Task 6: Metadata-Only CSV Detection and Local Opening

**Files:**
- Create: `src/lvms_stat/downloads.py`
- Test: `tests/test_downloads.py`

**Interfaces:**
- Consumes: configured absolute `download_directory`.
- Produces: `FileStamp(size: int, modified_ns: int)`, `CsvArrivalDetector.start()`, `poll() -> DownloadStatus`, `detected_path() -> Path | None`, and `open_local(path: Path, *, opener: Callable[[str], object] = os.startfile) -> None` on Windows.

- [ ] **Step 1: Write failing temporary-filesystem tests**

Test zero candidates, a file existing before `start`, uppercase/lowercase `.csv`, stability across two polls, a growing file, multiple new files, moved/deleted detected files, and non-CSV exclusion. Patch `Path.open`, `Path.read_bytes`, and `Path.read_text` to raise if called during detection.

Test local opening with an injected callable:

```python
opened: list[str] = []
open_local(csv_path, opener=opened.append)
self.assertEqual(opened, [str(csv_path)])
```

Reject relative paths, non-CSV paths, missing files, and directories without including the path in `DownloadError.__str__`.

- [ ] **Step 2: Run the tests to verify RED**

Run: `python -m unittest tests.test_downloads -v`

Expected: module import failure.

- [ ] **Step 3: Implement metadata-only detection**

Use `Path.iterdir`, `Path.is_file`, and `Path.stat` only. Snapshot a mapping from resolved candidate path to `FileStamp`; do not hash or open. A new candidate becomes stable only after two consecutive identical stamps. Model status as:

```python
class DownloadStatus(StrEnum):
    WAITING = "waiting"
    DETECTED = "detected"
    AMBIGUOUS = "ambiguous"
    MISSING = "missing"
```

Keep the detected absolute path private inside the service; expose it only through `detected_path` for the explicit open command. Never put it in `repr`, status text, workflow JSON, or exceptions.

- [ ] **Step 4: Run focused/full tests**

Run the focused and full suites. Expected: all pass and content-read traps remain untouched.

- [ ] **Step 5: Commit download handling**

```powershell
git add -- src/lvms_stat/downloads.py tests/test_downloads.py
git commit -m "feat: detect CSV arrival without reading contents"
```

### Task 7: Background Recording Service

**Files:**
- Create: `src/lvms_stat/recording_service.py`
- Test: `tests/test_recording_service.py`

**Interfaces:**
- Consumes: `AppConfig`, existing `EdgeProcess/CdpConnection/BrowserPage`, `RecorderSession`, and `CsvArrivalDetector`.
- Produces: `ServiceEventKind`, `ServiceEvent`, `RecordingService.start(config)`, `request_stop()`, `events() -> Queue[ServiceEvent]`, `open_detected_csv()`, and `close()`.

- [ ] **Step 1: Write failing service tests with injected fakes**

Build fakes for Edge, target discovery, connection, page, recorder, and detector. Verify start emits `STARTED`, then sanitized `STEPS`, then `DOWNLOAD_DETECTED`; stop closes the connection and only the tracked Edge child. Verify unexpected origin/listener errors emit one categorical `FAILED` event without raw exception text. Verify a second simultaneous start is rejected.

Use a synchronous injected worker for deterministic tests:

```python
service = RecordingService(dependencies=fakes, worker_submit=lambda fn: fn())
service.start(config)
events = drain(service.events())
self.assertEqual(
    [event.kind for event in events],
    [ServiceEventKind.STARTED, ServiceEventKind.STEPS, ServiceEventKind.DOWNLOAD_DETECTED],
)
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `python -m unittest tests.test_recording_service -v`

Expected: module import failure.

- [ ] **Step 3: Implement the supervised worker loop**

The production submitter starts one non-daemon `threading.Thread`. The normal recording portion of the worker is:

```python
detector.start()
edge = edge_start(config.profile_directory)
target = target_wait(edge.port)
connection = connection_open(target)
page = page_factory(connection)
page.navigate(config.landing_url, config.expected_origin, timeout_seconds=120)
recorder = recorder_factory(page, config.expected_origin)
recorder.install()
emit(ServiceEvent.started())
while not stop_event.wait(0.25):
    emit_steps(recorder.poll())
    status = detector.poll()
    if status is DownloadStatus.DETECTED:
        emit(ServiceEvent.download_detected())
        break
```

`request_stop` immediately disables browser-event polling and emits `STOPPED`, then checks only download metadata for up to 10 seconds using an injected monotonic clock. Detection during that grace period emits `DOWNLOAD_DETECTED`; expiry leaves the workflow in STOPPED. `close` bypasses the grace period, requests immediate worker exit, and joins with a bounded timeout.

Use `try/finally` for connection and child Edge cleanup. Map known failures to fixed enum categories. Do not put arbitrary exception text, paths, origins, event payloads, or browser messages into `ServiceEvent`.

- [ ] **Step 4: Run focused/full tests**

Run focused and full suites. Expected: all pass and no test launches a real thread unless explicitly testing stop/join semantics with bounded timeouts.

- [ ] **Step 5: Commit service orchestration**

```powershell
git add -- src/lvms_stat/recording_service.py tests/test_recording_service.py
git commit -m "feat: coordinate supervised recording lifecycle"
```

### Task 8: UI-Independent Application Controller

**Files:**
- Create: `src/lvms_stat/app_controller.py`
- Test: `tests/test_app_controller.py`

**Interfaces:**
- Consumes: `RecordingService`, workflow state/model functions, and `WorkflowStore`.
- Produces: `RecorderView` protocol and `AppController(view, service, store)` methods `start(name, notes)`, `stop()`, `handle_service_event(event)`, `assign_role(step_id, role)`, `save()`, `open_csv()`, and `close()`.

- [ ] **Step 1: Write failing controller tests using a fake view**

The fake view records rendered state without Tkinter. Verify blank/oversized names are rejected, the privacy warning is shown before start, valid service events append only typed `WorkflowStep` objects, role assignment works only after stop, save is explicit, and close during recording asks whether sanitized steps should be retained.

```python
controller.start("Weekly report", "Defined Reports export")
self.assertEqual(view.state, RecorderState.STARTING)
controller.handle_service_event(ServiceEvent.started())
self.assertEqual(view.state, RecorderState.RECORDING)
```

Verify `open_csv` is disabled until a detection event and controller-visible messages contain no path, filename, URL, or raw error.

- [ ] **Step 2: Run the tests to verify RED**

Run: `python -m unittest tests.test_app_controller -v`

Expected: module import failure.

- [ ] **Step 3: Implement the controller and view contract**

Define the view protocol around state, steps, and fixed messages rather than individual widget calls:

```python
class RecorderView(Protocol):
    def render(self, model: ViewModel) -> None: ...
    def confirm_privacy_boundary(self) -> bool: ...
    def confirm_keep_incomplete(self) -> bool: ...
    def show_message(self, message: UiMessage) -> None: ...
```

`ViewModel` contains workflow name/notes, `RecorderState`, sanitized steps, and booleans `can_start`, `can_stop`, `can_save`, and `can_open_csv`. It contains no filesystem path or browser payload. The controller is the only component allowed to transition states and call storage/open services.

- [ ] **Step 4: Run focused/full tests**

Run focused and full suites. Expected: all pass.

- [ ] **Step 5: Commit the controller**

```powershell
git add -- src/lvms_stat/app_controller.py tests/test_app_controller.py
git commit -m "feat: control recorder application states"
```

### Task 9: Tkinter Window and CLI Command

**Files:**
- Create: `src/lvms_stat/tk_app.py`
- Modify: `src/lvms_stat/__main__.py`
- Modify: `tests/test_cli.py`
- Create: `tests/test_tk_app.py`

**Interfaces:**
- Consumes: `AppController`, `RecorderView`, `load_app_config`, and service/store factories.
- Produces: `load_tkinter(importer=importlib.import_module)`, `TkRecorderView`, `run_app(config_path: Path) -> int`, and CLI `app --config PATH`.

- [ ] **Step 1: Write failing import/CLI/presentation tests**

Assert the parser exposes `app`, dispatches it to an injected `app_runner`, and leaves existing probe/inspect dispatch unchanged. Test `load_tkinter` with injected success and import failure. Test pure `format_step(step) -> str` output:

```python
self.assertEqual(
    format_step(field_step),
    "3. Edit field: From date [value not recorded]",
)
```

Assert formatting cannot include a value, path, URL, filename, or unknown field.

- [ ] **Step 2: Run the tests to verify RED**

Run: `python -m unittest tests.test_cli tests.test_tk_app -v`

Expected: missing Tk module/app command behavior.

- [ ] **Step 3: Implement the thin Tkinter adapter**

Build one `Tk` root with ttk widgets for name, notes, state, Start, Stop, Save review, numbered step list, parameter-role selector, CSV status, and Open CSV locally. Use `root.after(100, poll_service_events)` so all widget updates remain on the main thread. Button handlers call controller methods only.

Change `main` to accept separate injected runners:

```python
def main(
    argv: Sequence[str] | None = None,
    *,
    probe_runner: Callable[..., int] = run_probe,
    app_runner: Callable[[Path], int] = run_app,
) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.command == "app":
        return app_runner(arguments.config)
    return probe_runner(arguments.config, inspect=arguments.command == "inspect")
```

If Tkinter import or root creation fails, return `2` after printing only `LVMS-STAT app is unavailable in this Python installation.` Do not print raw Tcl/Python exception text.

- [ ] **Step 4: Run focused/full tests and CLI help**

Run:

```powershell
python -m unittest tests.test_cli tests.test_tk_app -v
python -m unittest discover -s tests -t . -v
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m lvms_stat --help
python -m lvms_stat app --help
```

Expected: all tests pass and help lists `probe`, `inspect`, and `app`; tests do not open a real window.

- [ ] **Step 5: Commit the desktop shell**

```powershell
git add -- src/lvms_stat/tk_app.py src/lvms_stat/__main__.py tests/test_cli.py tests/test_tk_app.py
git commit -m "feat: add local workflow recorder window"
```

### Task 10: Integrated Runbook and Privacy Verification

**Files:**
- Modify: `README.md`
- Create: `docs/work-computer-recorder.md`
- Modify: `tests/test_recording_service.py`
- Modify: `tests/test_app_controller.py`

**Interfaces:**
- Consumes: all preceding tasks.
- Produces: documented `python -m lvms_stat app --config config.json` supervised workflow and an end-to-end synthetic acceptance test.

- [ ] **Step 1: Write the failing synthetic acceptance test**

Drive the controller with a synchronous fake service that emits two safe clicks, two field edits, Export, and one detected fake CSV. Assert final state, review formatting, role assignment, and saved JSON. Concatenate UI messages and serialized JSON and assert:

```python
for forbidden in (
    "15.08.2026", "20.08.2026", "FORBIDDEN-TYPED-VALUE", "JSESSIONID",
    "https://", ".csv", str(temp_root),
):
    self.assertNotIn(forbidden.lower(), combined_output.lower())
```

The synthetic inputs must use non-clinical labels such as `Example report`, `From date`, `To date`, and `Export`.

- [ ] **Step 2: Run the acceptance test to verify RED**

Run the new named acceptance test. Expected: fail until the final event-to-view/store integration is wired exactly as specified.

- [ ] **Step 3: Complete integration and documentation**

Make the minimal wiring corrections exposed by the acceptance test. Update README scope and create a runbook that covers:

- checking `python -c "import tkinter; print(tkinter.TkVersion)"`;
- adding ignored download/workflow directories to local config;
- confirming `git check-ignore config.json`;
- launching the app through Python;
- using non-sensitive workflow names/notes;
- starting/stopping recording and assigning date roles;
- confirming no typed values appear in the review;
- interpreting zero/one/multiple CSV detection;
- opening the CSV locally without implying the app read it;
- closing Edge and reviewing locally; and
- never sharing workflow JSON, CSV, screenshots, profiles, internal output, or diagnostics.

- [ ] **Step 4: Run the complete verification gate**

Run:

```powershell
python -m unittest discover -s tests -t . -v
python -m compileall -q src tests
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m lvms_stat --help
git diff --check
git status --short
git ls-files
git grep -n -i -E "JSESSIONID=|LWSSO_COOKIE_KEY=|MRHSession=|Authorization:|Cookie:" -- ':!docs/superpowers/plans/*' ':!docs/work-computer-recorder.md' ':!docs/work-computer-probe.md'
```

Expected: tests and compilation succeed; CLI help loads; diff check is clean; only intended code/docs/tests are modified; the credential scan returns no match. Manually confirm no tracked `config.json`, workflow JSON, browser profile, CSV/XLS/HAR, internal host, or real report identifier exists.

- [ ] **Step 5: Commit the integrated recorder documentation**

```powershell
git add -- README.md docs/work-computer-recorder.md tests/test_recording_service.py tests/test_app_controller.py
git commit -m "docs: add supervised recorder runbook"
```

- [ ] **Step 6: Review before any live work-computer test**

Use the code-review and security-hardening gates on the complete diff. Run the verification gate again after every review fix. Do not perform the live LVMS integration from a non-authorised computer, and do not place any live result in GitHub or the Codex conversation.
