# LVMS-STAT Edge Connectivity and Inspector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python command that visibly launches managed Edge with a dedicated profile, verifies an HTTPS LVMS landing origin through normal SSO, and prints sanitized fixed-control metadata without accessing patient data or browser credentials.

**Architecture:** Pure Python modules separate configuration validation, Edge process lifecycle, CDP transport, and privacy-safe inspection. Every external boundary is injectable for synthetic unit tests; the real integration command remains visible, loopback-only, and fail-closed.

**Tech Stack:** Python 3.11+, standard library, `websocket-client>=1.8,<2`, `unittest`, Microsoft Edge DevTools Protocol.

**Spec:** `docs/superpowers/specs/2026-08-20-edge-inspector-design.md`

## Global Constraints

- Never commit or print patient data, cookies, tokens, request headers, full internal URLs, HAR files, screenshots, CSV exports, or authenticated Edge profiles.
- Bind the DevTools endpoint only to `127.0.0.1` and select an ephemeral port.
- Use a visible dedicated Edge profile outside the Git repository; headless operation is forbidden.
- Accept only an HTTPS landing URL with no query, fragment, or embedded credentials.
- Inspect fixed control metadata only; omit password controls and all control values.
- Do not change Edge, Ivanti, registry, or organisational policy.
- Do not execute or download an LVMS report in this increment.

---

### Task 1: Package foundation and validated local configuration

**Files:**
- Create: `pyproject.toml`
- Create: `config.example.json`
- Create: `src/lvms_stat/__init__.py`
- Create: `src/lvms_stat/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `ProbeConfig(landing_url: str, expected_origin: str, profile_directory: Path)`
- Produces: `load_config(path: Path, *, repository_root: Path) -> ProbeConfig`
- Produces: `validate_config(raw: Mapping[str, object], *, repository_root: Path) -> ProbeConfig`

- [ ] **Step 1: Write the failing configuration tests**

```python
class ConfigTests(unittest.TestCase):
    def test_accepts_https_landing_url_and_external_profile(self):
        config = validate_config(
            {
                "landing_url": "https://lvms.example.invalid/clims/",
                "profile_directory": str(self.temp_root / "profile"),
            },
            repository_root=self.repo_root,
        )
        self.assertEqual(config.expected_origin, "https://lvms.example.invalid")

    def test_rejects_query_fragment_credentials_and_repository_profile(self):
        invalid_urls = (
            "http://lvms.example.invalid/",
            "https://user:pass@lvms.example.invalid/",
            "https://lvms.example.invalid/?token=x",
            "https://lvms.example.invalid/#patient",
        )
        for landing_url in invalid_urls:
            with self.subTest(landing_url=landing_url):
                with self.assertRaises(ConfigError):
                    validate_config(
                        {"landing_url": landing_url, "profile_directory": str(self.temp_root)},
                        repository_root=self.repo_root,
                    )
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest tests.test_config -v`

Expected: import failure for missing `lvms_stat.config`.

- [ ] **Step 3: Implement the minimal immutable configuration model and validator**

```python
@dataclass(frozen=True)
class ProbeConfig:
    landing_url: str
    expected_origin: str
    profile_directory: Path

def validate_config(raw: Mapping[str, object], *, repository_root: Path) -> ProbeConfig:
    landing_url = _required_text(raw, "landing_url")
    parsed = urlsplit(landing_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ConfigError("landing_url must be an HTTPS URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigError("landing_url must not contain credentials, query, or fragment")
    profile = Path(_required_text(raw, "profile_directory")).expanduser().resolve()
    if profile == repository_root.resolve() or repository_root.resolve() in profile.parents:
        raise ConfigError("profile_directory must be outside the repository")
    return ProbeConfig(landing_url, f"https://{parsed.netloc}", profile)
```

- [ ] **Step 4: Run configuration tests and verify GREEN**

Run: `python -m unittest tests.test_config -v`

Expected: all configuration tests pass.

- [ ] **Step 5: Commit the package/configuration slice**

```powershell
git add -- pyproject.toml config.example.json src/lvms_stat/__init__.py src/lvms_stat/config.py tests/test_config.py
git commit -m "feat: validate privacy-safe probe configuration"
```

---

### Task 2: Privacy-safe control sanitizer

**Files:**
- Create: `src/lvms_stat/inspection.py`
- Create: `tests/test_inspection.py`

**Interfaces:**
- Produces: `SAFE_CONTROL_FIELDS: tuple[str, ...]`
- Produces: `sanitize_controls(raw: object, *, max_controls: int = 200, max_text_length: int = 120) -> list[dict[str, str]]`
- Produces: `CONTROL_INSPECTION_SCRIPT: str`

- [ ] **Step 1: Write tests that prove values and password controls cannot escape**

```python
class InspectionTests(unittest.TestCase):
    def test_allowlists_metadata_and_truncates_text(self):
        result = sanitize_controls([
            {"tag": "BUTTON", "id": "export", "text": "X" * 200}
        ], max_text_length=12)
        self.assertEqual(result, [{"tag": "BUTTON", "id": "export", "text": "XXXXXXXXXXXX"}])

    def test_omits_password_controls(self):
        result = sanitize_controls([
            {"tag": "INPUT", "type": "password", "id": "secret"},
            {"tag": "BUTTON", "text": "Export"},
        ])
        self.assertEqual(result, [{"tag": "BUTTON", "text": "Export"}])

    def test_rejects_non_list_payload_and_caps_control_count(self):
        with self.assertRaises(InspectionError):
            sanitize_controls({"value": "unexpected"})
        self.assertEqual(len(sanitize_controls([{"tag": "BUTTON"}] * 5, max_controls=2)), 2)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest tests.test_inspection -v`

Expected: import failure for missing `lvms_stat.inspection`.

- [ ] **Step 3: Implement strict allowlisting and the fixed DOM enumeration expression**

```python
SAFE_CONTROL_FIELDS = ("tag", "id", "name", "type", "role", "label", "text", "frame")

def sanitize_controls(raw: object, *, max_controls: int = 200, max_text_length: int = 120):
    if not isinstance(raw, list):
        raise InspectionError("inspector result must be a list")
    safe = []
    for item in raw[:max_controls]:
        if not isinstance(item, dict) or str(item.get("type", "")).lower() == "password":
            continue
        control = {}
        for field in SAFE_CONTROL_FIELDS:
            value = item.get(field)
            if isinstance(value, str) and value.strip():
                control[field] = value.strip()[:max_text_length]
        if control:
            safe.append(control)
    return safe
```

The JavaScript expression must select only visible `button`, `a`, `input`, `select`, `textarea`, and role-based interactive controls; it must construct new objects containing only `SAFE_CONTROL_FIELDS` and never read `.value`, `href`, `src`, cookies, storage, table cells, or network state.

- [ ] **Step 4: Run inspection tests and verify GREEN**

Run: `python -m unittest tests.test_inspection -v`

Expected: all inspection tests pass.

- [ ] **Step 5: Commit the sanitizer slice**

```powershell
git add -- src/lvms_stat/inspection.py tests/test_inspection.py
git commit -m "feat: sanitize browser control metadata"
```

---

### Task 3: Managed Edge discovery and loopback-only launch

**Files:**
- Create: `src/lvms_stat/edge.py`
- Create: `tests/test_edge.py`

**Interfaces:**
- Produces: `find_edge_executable(environ: Mapping[str, str], which: Callable[[str], str | None]) -> Path`
- Produces: `reserve_loopback_port() -> int`
- Produces: `build_edge_arguments(edge: Path, profile: Path, port: int) -> list[str]`
- Produces: `EdgeProcess.start(profile: Path) -> EdgeProcess`
- Produces: `EdgeProcess.close() -> None`

- [ ] **Step 1: Write tests for safe argument construction**

```python
class EdgeArgumentTests(unittest.TestCase):
    def test_builds_visible_loopback_only_dedicated_profile_launch(self):
        args = build_edge_arguments(Path("C:/Edge/msedge.exe"), Path("C:/Profiles/lvms"), 49152)
        self.assertIn("--remote-debugging-address=127.0.0.1", args)
        self.assertIn("--remote-debugging-port=49152", args)
        self.assertIn("--user-data-dir=C:\\Profiles\\lvms", args)
        self.assertNotIn("--headless", args)

    def test_rejects_non_ephemeral_or_non_loopback_configuration(self):
        with self.assertRaises(EdgeLaunchError):
            build_edge_arguments(Path("C:/Edge/msedge.exe"), Path("C:/Profiles/lvms"), 80)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest tests.test_edge -v`

Expected: import failure for missing `lvms_stat.edge`.

- [ ] **Step 3: Implement discovery, ephemeral-port reservation, arguments, and cleanup**

The process arguments must contain only the approved Edge executable, loopback debugging address, ephemeral port, dedicated profile, new visible window, startup suppression, and `about:blank`. `subprocess.Popen` receives an argument list, never a shell string, and uses `shell=False`.

`EdgeProcess.close()` first attempts a normal terminate/wait, then kills only the exact child process if the timeout expires. It never enumerates or closes unrelated Edge processes.

- [ ] **Step 4: Run Edge tests and verify GREEN**

Run: `python -m unittest tests.test_edge -v`

Expected: all Edge tests pass without launching a browser.

- [ ] **Step 5: Commit the Edge lifecycle slice**

```powershell
git add -- src/lvms_stat/edge.py tests/test_edge.py
git commit -m "feat: launch managed Edge on loopback CDP"
```

---

### Task 4: Minimal synchronous CDP client

**Files:**
- Create: `src/lvms_stat/cdp.py`
- Create: `tests/test_cdp.py`

**Interfaces:**
- Produces: `discover_page(port: int, *, opener: Callable[..., object] = urlopen) -> PageTarget`
- Produces: `CdpConnection.call(method: str, params: Mapping[str, object] | None = None, *, timeout_seconds: float = 10) -> dict[str, object]`
- Produces: `BrowserPage.navigate(url: str, expected_origin: str, timeout_seconds: float = 30) -> PageIdentity`
- Produces: `BrowserPage.inspect_controls() -> list[dict[str, str]]`

- [ ] **Step 1: Write protocol tests using fake HTTP and WebSocket boundaries**

```python
class CdpConnectionTests(unittest.TestCase):
    def test_matches_response_to_command_id(self):
        socket = FakeSocket(['{"id":1,"result":{"result":{"value":"ready"}}}'])
        connection = CdpConnection(socket)
        result = connection.call("Runtime.evaluate", {"expression": "document.readyState"})
        self.assertEqual(result["result"]["value"], "ready")

    def test_rejects_unexpected_origin_without_returning_full_url(self):
        page = BrowserPage(FakeCdp(responses_for_origin("https://unexpected.invalid")))
        with self.assertRaises(UnexpectedOriginError) as caught:
            page.navigate("https://lvms.example.invalid/", "https://lvms.example.invalid")
        self.assertNotIn("?", str(caught.exception))
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest tests.test_cdp -v`

Expected: import failure for missing `lvms_stat.cdp`.

- [ ] **Step 3: Implement bounded HTTP discovery and command-response matching**

HTTP discovery may access only `http://127.0.0.1:<ephemeral-port>/json/list`. The WebSocket URL must parse to a loopback hostname and the expected ephemeral port before connection. The CDP client must reject malformed JSON, protocol error objects, responses larger than the configured bound, and timeouts with sanitized exceptions.

`BrowserPage.navigate` enables `Page` and `Runtime`, invokes `Page.navigate`, polls `document.readyState`, then evaluates `location.origin` and `document.title`. It returns only `PageIdentity(origin, title)` with the title length capped.

`BrowserPage.inspect_controls` evaluates only `CONTROL_INSPECTION_SCRIPT`, requires a by-value JSON result, and passes it through `sanitize_controls` before returning.

- [ ] **Step 4: Run CDP tests and verify GREEN**

Run: `python -m unittest tests.test_cdp -v`

Expected: all CDP tests pass with no network or browser access.

- [ ] **Step 5: Commit the CDP slice**

```powershell
git add -- src/lvms_stat/cdp.py tests/test_cdp.py
git commit -m "feat: add bounded local Edge CDP client"
```

---

### Task 5: User-supervised probe command and work-computer runbook

**Files:**
- Create: `src/lvms_stat/probe.py`
- Create: `src/lvms_stat/__main__.py`
- Create: `tests/test_probe.py`
- Create: `README.md`
- Create: `docs/work-computer-probe.md`

**Interfaces:**
- Produces: `run_probe(config_path: Path, *, inspect: bool = False, dependencies: ProbeDependencies | None = None) -> int`
- Produces CLI: `python -m lvms_stat probe --config config.json`
- Produces CLI: `python -m lvms_stat inspect --config config.json`

- [ ] **Step 1: Write orchestration tests with fake Edge and browser page**

```python
class ProbeTests(unittest.TestCase):
    def test_probe_reports_only_origin_and_capped_title(self):
        output = io.StringIO()
        result = run_probe(
            self.config_path,
            dependencies=fake_dependencies(identity=PageIdentity("https://lvms.example.invalid", "LVMS")),
            output=output,
        )
        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), "Connected: https://lvms.example.invalid — LVMS\n")

    def test_failure_is_sanitized_and_always_closes_child_edge(self):
        dependencies = fake_dependencies(error=RemoteDebuggingUnavailable())
        result = run_probe(self.config_path, dependencies=dependencies, output=io.StringIO())
        self.assertEqual(result, 2)
        self.assertTrue(dependencies.edge.closed)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest tests.test_probe -v`

Expected: import failure for missing `lvms_stat.probe`.

- [ ] **Step 3: Implement CLI orchestration with `finally` cleanup**

The default command performs connectivity only. Inspection requires the explicit `inspect` subcommand and a console confirmation that the current page contains no patient table. The CLI prints controls as line-oriented JSON containing only sanitized allowlisted fields.

Exit codes are `0` success, `2` configuration/policy/connectivity failure, and `130` user cancellation. Raw tracebacks are available only to developers through tests; production console output is categorized and non-sensitive.

- [ ] **Step 4: Document installation and the harmless integration procedure**

The runbook must instruct the user to check `edge://policy` without changing it, create `config.json` outside Git, start with `probe`, use `inspect` only on a page with no patient table, and share only sanitizer output. It must explicitly prohibit copied headers, cURL, HAR, screenshots, report files, and profile directories.

- [ ] **Step 5: Run the complete test suite and inspect CLI help**

Run: `python -m unittest discover -s tests -t . -v`

Expected: all tests pass without launching Edge or contacting any network.

Run: `python -m lvms_stat --help`

Expected: help lists `probe` and `inspect`; no internal hostname appears.

- [ ] **Step 6: Run repository hygiene checks and commit**

```powershell
git diff --check
git status --short
git add -- README.md docs/work-computer-probe.md src/lvms_stat/probe.py src/lvms_stat/__main__.py tests/test_probe.py
git diff --cached
git commit -m "feat: add supervised LVMS Edge probe"
```

---

### Task 6: Final verification and handoff package

**Files:**
- Modify: `README.md`
- Modify: `docs/work-computer-probe.md`

**Interfaces:**
- Consumes: all interfaces from Tasks 1–5.
- Produces: a clean repository ready for a user-supervised work-computer probe.

- [ ] **Step 1: Run tests from a clean Python invocation**

Run: `python -m unittest discover -s tests -t . -v`

Expected: all tests pass with no warnings, network access, or Edge process.

- [ ] **Step 2: Verify tracked-file and secret boundaries**

Run: `git ls-files`

Expected: no `config.json`, CSV/XLSX/HAR, authenticated profile, download, raw-report, or processed-report path.

Run: `git grep -n -i -E "JSESSIONID=|LWSSO_COOKIE_KEY=|MRHSession=|Authorization:|Cookie:" -- ':!docs/superpowers/plans/*' ':!docs/work-computer-probe.md'`

Expected: no matches.

- [ ] **Step 3: Review the final diff and status**

Run: `git status --short`

Expected: clean working tree after any documentation correction is committed.

- [ ] **Step 4: Hand off only the probe instructions**

The user runs the probe on the OUS computer. Development stops if Edge policy blocks remote debugging, SSO requires an unapproved authentication change, or the inspector cannot avoid patient-bearing page content.
