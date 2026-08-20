# LVMS-STAT Safe Workflow Recorder Design

## Purpose

Add a simple local desktop application that lets an authorised user describe one LVMS Defined Reports workflow, start a visible Edge session, automatically record the safe browser actions they perform, stop after the normal CSV export, and review the sanitized sequence.

This increment proves that LVMS interactions can be represented as stable, privacy-safe steps. It does not replay a workflow, parse a report, generate statistics, schedule work, or send data to Power BI.

## Scope and Success Criteria

The first recorder supports one workflow at a time. The user can:

1. enter a non-sensitive workflow name and notes;
2. start a recording in the dedicated managed Edge session;
3. navigate through the configured LVMS origin and perform the report workflow normally;
4. type report parameters, including From and To dates, without their values being recorded;
5. click Export and allow LVMS to create its normal CSV;
6. review the sanitized action sequence in the desktop app;
7. label edited fields as From date, To date, or another future parameter;
8. see that a new CSV was detected without the app reading its contents; and
9. ask Windows to open the detected CSV in its approved default application.

Success means the review accurately describes the control sequence needed for the chosen report while no typed values, patient data, report rows, credentials, network traffic, or browser storage reach logs, saved workflow data, tests, Git, or GitHub.

## Non-Goals

- Replaying recorded steps.
- Storing or automatically supplying date values.
- Supporting relative dates such as previous week.
- Supporting multiple named workflows.
- Parsing, previewing, validating, transforming, or aggregating CSV contents.
- Scheduling or unattended/headless execution.
- Calling an LVMS API or replaying HTTP requests.
- Recording SSO interactions.
- Capturing screenshots, video, clipboard contents, keystrokes, cookies, storage, request headers, response bodies, download URLs, or page tables.

These are separate increments that require new design and review.

## Recommended Architecture

The existing Python package remains the single process. A Tkinter desktop window coordinates four isolated components:

- **Application controller:** owns the state machine and connects UI commands to services.
- **Managed Edge session:** reuses the visible, dedicated-profile, loopback-only CDP launcher and origin checks already implemented.
- **Safe action recorder:** installs a narrow event listener on approved LVMS documents and converts candidate browser events into sanitized workflow steps.
- **CSV arrival detector:** observes filesystem metadata in an explicitly configured download directory and reports only whether a new CSV appeared.

Tkinter is preferred because it is included with standard Windows Python installations and avoids another UI runtime, browser driver, extension, Node.js process, or packaged executable. Startup must check that Tkinter is available and return a clear instruction if the organisation-provided Python build omits it.

The app is launched with Python, for example through a future `python -m lvms_stat app --config config.json` command. It is not packaged as an `.exe`.

## Application States

The controller uses explicit states rather than inferring state from widgets:

1. **READY:** workflow description is editable; no browser recording is active.
2. **STARTING:** Edge and the recorder connection are being established.
3. **RECORDING:** approved events may be accepted and shown; workflow description is locked.
4. **STOPPED:** no more events are accepted; recorded steps can be reviewed and parameter labels edited.
5. **DOWNLOAD_DETECTED:** a single new CSV has been identified and may be opened locally.
6. **ERROR:** recording has failed closed; sanitized diagnostics and any already accepted safe steps remain available for review.

Only valid transitions are enabled in the UI. Closing the application during STARTING or RECORDING first stops event acceptance, closes the tracked Edge child process, and then asks whether already sanitized steps should be retained locally. An incomplete recording is not saved automatically.

## Desktop Interface

The first window contains:

- workflow name;
- non-sensitive notes;
- current status;
- Start recording and Stop buttons;
- a numbered, read-only list of sanitized steps;
- parameter-role controls for edited fields after recording;
- CSV status and Open CSV locally button; and
- a clear statement that replay, scheduling, and data processing are not active.

The app never embeds an LVMS page or CSV preview. Edge and the default CSV application remain separate visible windows. The interface must not show a downloaded filename because filenames are not guaranteed to be identifier-free.

## Recording Data Flow

When Start recording is pressed:

1. configuration is validated;
2. the CSV detector snapshots eligible file metadata in the approved download directory;
3. the existing launcher starts a visible managed Edge child with the dedicated profile;
4. the controller navigates to the clean configured landing URL;
5. normal SSO may occur visibly, but events are accepted only after the configured LVMS origin is reached;
6. the recorder installs its fixed listener in the approved top-level document and approved same-origin frames; and
7. sanitized steps are appended to the review list as the user works.

The listener observes only these candidate event categories:

- activation of buttons, links, menu items, checkboxes, and radio buttons;
- safe selection changes;
- completion of editing in a permitted text-like control; and
- document navigation needed to re-establish the listener.

It does not transmit the DOM event object. It constructs a small allowlisted candidate containing only event kind and control identity metadata. Python then applies a second, independent sanitizer before creating a step.

For a text-like control, the recorder emits `field_edited` only when editing completes. It never reads or transports the control's `value`, individual key events, key count, selection, autocomplete state, or clipboard data. After stopping, the user may assign the safe semantic role `from_date`, `to_date`, or `other_parameter` to that field. Version 1 stores no parameter value.

## Safe Control Identity

A recorded action needs enough identity for human review and possible future replay without collecting page content. Candidate identity fields are restricted to:

- element tag;
- safe input/control type;
- fixed `id` or `name` when present;
- ARIA role;
- short accessible label or control text; and
- a bounded structural locator built only from allowlisted attributes and element positions.

Every string and list has a strict size limit. Unknown fields cause candidate rejection rather than being ignored silently. Password and hidden controls are rejected. Any candidate containing forbidden keys such as `value`, `href`, `src`, `url`, `cookie`, `token`, `authorization`, or arbitrary text/content fields is rejected.

Controls are rejected if they are inside or owned by a table, grid, treegrid, patient/results container, editable document region, or another excluded area. The original page origin is checked immediately before listener installation and again before accepting each event batch. Events from SSO or unexpected origins are discarded.

The display label is informational only. Future replay must not assume that visible text is a stable selector; selector stability will be evaluated after the supervised recording.

## Navigation and Listener Lifecycle

LVMS may replace documents, frames, or application views during a workflow. The recorder therefore treats listener installation as renewable:

- detect top-level navigation through CDP page lifecycle signals;
- wait until the configured origin and document readiness are re-established;
- install a fresh listener in approved documents;
- use a recording-session nonce to reject late events from an old document; and
- never enable broad network interception to infer navigation.

If the listener cannot be safely re-established, recording stops with a sanitized message. The app does not continue with a partially monitored workflow.

## CSV Arrival Detection and Local Opening

The download directory is an explicit local configuration value and must be outside the repository. At recording start, the detector records only bounded filesystem metadata needed to distinguish later arrivals. It does not open or hash existing files.

During recording and for a short bounded period after Stop, it looks for newly created regular files with a `.csv` suffix. A candidate must be stable across consecutive metadata checks so a partially written download is not offered.

- No candidate: the review remains usable and reports that no CSV was detected.
- One candidate: the state becomes DOWNLOAD_DETECTED without displaying its filename or contents.
- Multiple candidates: the app refuses to guess and instructs the user to remove the ambiguity locally.
- Candidate moved or deleted: Open CSV locally is disabled.

Open CSV locally performs no read. After an explicit user click and local warning, it asks Windows to open the exact detected path with the registered default application. Failure is reported without printing the full path. This feature neither approves the file's use nor changes organisational handling requirements.

## Local Workflow Storage

Only explicitly saved, fully sanitized workflow metadata is persisted. The storage directory is beneath the current user's Local AppData and outside the repository. A saved record may contain:

- schema version;
- workflow name and notes after validation;
- creation/update timestamps;
- ordered sanitized steps;
- user-assigned parameter roles; and
- a completion flag indicating whether a CSV was detected.

It must not contain typed values, filenames, absolute paths, URLs, internal origins, user identifiers, page titles, raw browser events, exception strings, CSV metadata beyond the completion flag, or any report contents. Workflow name and notes are user-authored and therefore receive a prominent warning not to include patient, sample, employee, or session information.

Saving is explicit. Atomic replacement prevents a crash from leaving a partial JSON file. Versioned schema validation is required when loading.

## Error Handling

Errors are mapped to non-sensitive categories:

- invalid local configuration;
- Tkinter unavailable;
- managed Edge unavailable or blocked;
- connection or navigation timeout;
- unexpected origin;
- recorder listener unavailable;
- unsafe event rejected;
- recording interrupted;
- download directory unavailable;
- no CSV detected;
- multiple CSV candidates;
- detected CSV no longer available; and
- local open request failed.

Unsafe individual events are discarded and counted without showing raw data. A high rejection count or any origin/listener integrity failure stops recording. Raw JavaScript, CDP payloads, paths, browser messages, and exception text are never written to the UI or persistent logs.

## Testing Strategy

Automated tests remain synthetic and must not launch Edge, contact LVMS, or create patient-like fixtures.

Tests cover:

- controller state transitions and invalid transition rejection;
- UI actions through injected fake services rather than a real display;
- event-category allowlisting;
- double sanitization and strict schema rejection;
- typed-value and forbidden-key non-propagation into UI, persistence, and diagnostics;
- table/grid/password/hidden/unexpected-origin rejection;
- recording nonce handling and safe listener reinjection after synthetic navigation;
- field-role assignment without values;
- filesystem snapshot and stable single-CSV detection using temporary files;
- zero, one, multiple, incomplete, moved, and deleted CSV cases;
- an injected local-open boundary that never reads file bytes;
- explicit save, atomic storage, and schema validation; and
- browser and recorder cleanup on stop, close, cancellation, and failure.

Repository checks scan tracked files for real configuration, workflow storage, browser profiles, CSV files, credentials, internal hosts, and forbidden artifacts.

## Supervised Work-Computer Validation

The first integration run is performed only on the authorised work computer:

1. use a non-patient Defined Reports page until the export action;
2. enter ordinary report parameters manually while confirming no values appear in the recorder;
3. complete the normal export;
4. confirm that the app shows a sanitized sequence and only Download detected;
5. inspect every displayed and saved step locally for unintended sensitive content;
6. open the CSV locally through the button and verify that the approved default application opens it; and
7. do not share the CSV, workflow file, screenshots, profile, or internal diagnostic output.

If an event cannot be represented without sensitive text or a stable safe identity, the recorder must omit it and the workflow is not yet eligible for replay.

## Delivery Sequence

Implementation should land in independently verified increments:

1. application state model and storage schema;
2. Tkinter shell backed by fake services;
3. strict browser-event schema and sanitizer;
4. CDP listener lifecycle and synthetic navigation tests;
5. CSV arrival detector and local-open boundary;
6. integrated record/review controller;
7. privacy-focused repository review and work-computer runbook.

Replay, relative dates, multiple workflows, CSV processing, and Power BI output remain later projects.
