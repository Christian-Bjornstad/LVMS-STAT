# LVMS CDP Integration Design

**Date:** 2026-08-21
**Status:** Proposed for implementation planning
**Branch:** `feature/lvms-cdp-integration`

## Objective

Prove and harden a privacy-safe path from the approved Python environment to a
managed Microsoft Edge instance and the LVMS defined-report interface. The first
delivery stops after reliable browser launch, SSO navigation, safe DOM discovery,
and a supervised metadata-only download test.

This design does not yet implement historical backfill, recurring scheduling,
deduplication, Excel generation, or Power BI refresh. Those are separate
subprojects that depend on this integration being reliable.

## Confirmed Environment

- The application is started from the approved `Python FELLES` environment.
- A separate existing project already starts the installed managed Edge directly
  from Python with a loopback-only Chrome DevTools Protocol (CDP) connection.
- That working pattern uses `msedge.exe`, a dedicated persistent browser profile,
  an ephemeral loopback port, `websocket-client`, and no WebDriver executable.
- Opening the LVMS base address in managed Edge normally completes organisation
  SSO without manual credential entry.
- LVMS defined reports are selected through report type, category, report ID, and
  report-specific parameter rows.
- Report generation can take several minutes and ends with a CSV download.

## Scope Decomposition

The overall project is divided into four ordered subprojects:

1. **CDP integration:** this design; launch Edge, reach LVMS, discover controls,
   and prove a supervised download boundary.
2. **Report automation:** select and execute configured report jobs through stable
   DOM identities.
3. **Local data pipeline:** archive raw files, normalize data, deduplicate rows,
   and produce a rebuildable analytics dataset.
4. **Operations:** historical backfill, daily or weekly scheduling, recovery, and
   Power BI consumption.

Only subproject 1 is authorized by this design.

## Recommended Architecture

### Normal path

```text
Python FELLES
  -> LVMS-STAT controller
  -> managed Edge executable
  -> dedicated LVMS browser profile
  -> loopback-only CDP connection
  -> clean LVMS landing URL
  -> organisation SSO
  -> safe DOM discovery
  -> supervised download metadata check
```

LVMS-STAT starts Edge directly. The managed-application launcher is not part of
the normal browser-control path because direct Edge CDP is already proven in the
same Python environment.

### Fallback path

The organisation's managed LVMS launcher remains a diagnostic fallback only. It
may be used to establish whether direct navigation and the managed shortcut reach
the same service, but LVMS-STAT must not attach to or terminate an Edge process it
did not start.

## Components and Boundaries

### Managed Edge launcher

The launcher locates the installed organisation-managed Edge executable and
starts it with:

- an ephemeral port in the operating system's dynamic range;
- a debugging address restricted to `127.0.0.1`;
- a matching local WebSocket origin;
- an absolute dedicated profile below the user's local application-data folder;
- first-run and default-browser prompts disabled;
- a visible window for supervised testing.

It retries only known transient broker handoff failures and closes only the
process and profile context it created.

### CDP transport

The transport communicates only with the reserved loopback endpoint. It validates
the scheme, host, port, target type, message size, and response structure before
using any DevTools result. Timeouts are bounded and errors are translated into
fixed, non-sensitive status messages.

### SSO navigation gate

The controller navigates to a clean HTTPS landing URL with no query string,
fragment, credentials, or session identifiers. Redirects may pass through
organisation SSO, but automation proceeds only after the page returns to the
configured expected origin.

The controller never logs redirect URLs. A timeout reports only whether Edge
failed to start, CDP was unavailable, SSO did not return, or the expected origin
was not reached.

### Safe LVMS discovery

The first integration slice discovers only the minimum metadata required to
identify the defined-report form:

- element type;
- stable ID, name, label, or accessible text;
- whether the control is visible, enabled, and editable;
- relative structural relationships needed to distinguish parameter rows.

The discovery layer excludes values, table or grid content, hidden controls,
password fields, content-editable regions, patient-, sample-, and result-like
containers, cookies, storage, network traffic, and page HTML.

### Download boundary

CDP configures a dedicated download inbox below an approved local data root. The
supervised download test may observe only:

- that a new `.csv` file appeared;
- the configured job identity, not the server-supplied path;
- file completion based on temporary-file disappearance and stable size;
- success, timeout, collision, or unexpected-file status.

The test does not open or parse the CSV. Later pipeline work will move and rename
the completed file using a deterministic job key and explicit date interval.

## Local Configuration

Real environment values are stored outside the repository in a user-local JSON
file. The repository contains only a placeholder example.

Local-only configuration includes:

- clean LVMS landing URL and expected origin;
- managed-application IDs used only for diagnostics;
- dedicated browser-profile directory;
- approved download inbox and future raw-data root;
- report IDs, parameter profiles, analysis-code lists, and output job keys.

Validation rejects credentials, query strings, fragments, relative paths,
repository-contained data directories, unknown parameter names, duplicate job
keys, malformed dates, empty analysis codes, and unsafe filename characters.

## Report Model Discovered for Later Work

A report job must be defined independently from its LVMS report ID because
multiple operational jobs may use the same report with different analysis-code
sets and output purposes.

Each future job will have:

- a unique job key;
- report type and category;
- report ID;
- an exact comma-separated analysis-code set;
- an explicit allowlist of parameter rows to populate;
- an explicit date interval;
- a deterministic local output name;
- a recurrence mode defined only in the operations subproject.

Some result reports expose additional date parameters. Fields not allowlisted by
the job remain blank; the automation never fills them by positional assumption.

## First Work-Computer Test

The first test is supervised and runs in two gates.

### Gate A: connectivity and safe discovery

1. Start LVMS-STAT manually through `Python FELLES`.
2. Launch the dedicated managed Edge profile with CDP.
3. Navigate to the clean LVMS landing URL.
4. Wait for SSO to return to the expected origin.
5. Navigate to the defined-report page using discovered DOM controls.
6. Confirm that report selectors and parameter rows can be identified without
   reading their values or surrounding data.
7. Stop without selecting or exporting a report.

### Gate B: supervised metadata-only download

Gate B runs only after Gate A passes.

1. Use one locally configured report job and an approved date interval.
2. Populate only the job's allowlisted fields.
3. Show a review summary containing job key, report ID, number of analysis codes,
   and date interval, but not the full analysis list.
4. Require an explicit local confirmation before export.
5. Wait for one completed CSV in the dedicated inbox.
6. Report metadata-only success and stop without opening or parsing the file.

## Error Handling

The controller fails closed with distinct outcomes:

- managed Edge executable not found;
- Edge process blocked or exited;
- CDP endpoint unavailable;
- CDP target malformed or outside loopback;
- SSO did not return before timeout;
- unexpected origin reached;
- defined-report controls not uniquely identifiable;
- page structure changed after discovery;
- export did not complete before timeout;
- multiple or unexpected files appeared;
- cleanup of owned resources was incomplete.

Retries are limited to transient Edge broker startup failures. Navigation,
selector, origin, and download-integrity failures require review rather than blind
repetition.

## Privacy and Security Requirements

- No patient, sample, result, report-row, credential, cookie, or session data may
  enter logs, screenshots, tests, source control, issue text, or pull requests.
- Browser profiles, local configuration, downloads, raw files, processed data,
  and operational logs remain on the approved work environment.
- Browser-profile directories are treated as authenticated secret material and
  must never be copied or committed.
- CDP is loopback-only and uses an ephemeral port per launch.
- The app never reuses or attaches to an unrelated Edge instance.
- Session-bearing URLs are neither stored nor displayed.
- Synthetic pages and fake report metadata are used for automated tests.
- A real CSV is not parsed until a separate local-data-pipeline design is
  approved.

## Testing Strategy

### Automated tests

- Edge discovery and command construction across managed installation paths;
- loopback and ephemeral-port enforcement;
- process ownership and bounded cleanup;
- retry behavior for transient broker failures;
- CDP discovery size, shape, host, port, and target validation;
- SSO redirect success, timeout, and unexpected-origin handling;
- safe control discovery and exclusion rules;
- unique-selector failure behavior;
- download completion, collision, timeout, and unexpected-file detection;
- log redaction and fixed error messages;
- configuration rejection for unsafe values and directories.

### Synthetic integration test

A local synthetic page reproduces the report-selector and parameter-row structure
without LVMS data. It verifies navigation, DOM selection, field population,
review-gate behavior, and a fake CSV download.

### Work-computer verification

The supervised gates above are recorded as pass/fail capability results only.
No session identifiers, screenshots, report values, or downloaded contents are
included in the repository.

## Acceptance Criteria

Subproject 1 is complete when:

1. LVMS-STAT starts through the approved Python environment.
2. It launches a dedicated managed Edge profile and establishes loopback CDP.
3. Organisation SSO reaches the configured LVMS origin without credential
   capture or logging.
4. The defined-report controls are uniquely discovered without reading sensitive
   content.
5. A supervised export produces exactly one stable CSV in the dedicated local
   inbox without the app opening or parsing it.
6. All automated and synthetic tests pass.
7. A security scan finds no real environment identifiers, session material, or
   patient data in the repository.

## Explicitly Deferred

- fully unattended startup of `Python FELLES`;
- Task Scheduler or recurring execution;
- historical backfill and interval chunking;
- CSV schema inspection and row-level deduplication;
- Excel workbook generation;
- Power BI refresh or publication;
- sanctioned API or database integration;
- management of real report-job configuration in source control.
