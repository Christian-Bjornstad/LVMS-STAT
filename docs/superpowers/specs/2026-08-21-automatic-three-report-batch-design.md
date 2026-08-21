# Automatic Three-Report Batch Design

## Status

Approved in conversation on 2026-08-21; written specification awaiting final review.

## Goal

Run three explicitly configured LVMS Defined Reports jobs in one visible, application-owned Microsoft Edge session. LVMS-STAT navigates from the clean `/clims` landing page, resolves the dynamic report form across same-origin frames, fills each job, exports it without an interactive confirmation, detects exactly one completed CSV, and gives that file a deterministic non-overwriting name before starting the next job.

The command invocation is the operator's authorization to export all listed jobs. No additional `INSPECT`, `DISCOVER`, or `EXPORT` prompt appears during the batch.

## Scope

This increment includes:

- automatic navigation to the Defined Reports page;
- structural page recognition using the validated top-document and frame controls;
- frame-aware discovery and interaction;
- staged selection of report type, category, and report ID;
- population of analysis codes and explicit From/To dates;
- three sequential jobs in one visible Edge session;
- exactly-one-file detection, deterministic rename, and duplicate refusal;
- sanitized progress and failure messages;
- synthetic end-to-end tests with same-origin frames and dynamic controls;
- a supervised work-computer acceptance run using short explicit dates.

This increment excludes:

- PyQt6 or other graphical UI work;
- Tkinter changes;
- PowerGate-driven or screen-coordinate automation;
- headless execution;
- recurring schedules or cron;
- automatic relative date calculation;
- historical backfill;
- CSV opening, parsing, aggregation, deduplication by report content, or Power BI refresh;
- API, cookie, request, or session replay.

## Validated Environment Assumptions

- Python Felles can start organisation-managed Edge directly.
- Edge accepts a dedicated profile beneath Local AppData.
- CDP is available on an operating-system-selected non-privileged loopback port.
- normal SSO reaches the configured expected origin from the clean `/clims` landing page;
- the final Defined Reports page exposes these sanitized structural controls:
  - top document: `SELECT#jobtypeselector` with the same name;
  - same-origin frame `_nav_frame1`: `BUTTON#clear` and `BUTTON#export`;
- two manually tested navigation routes produced the same final structure.

The structural names above are control metadata, not authentication or report data. The real hostname, job values, report IDs, analysis codes, dates, profile, contracts, and downloaded files remain only in ignored local configuration.

## Chosen Approach

Use a deterministic, frame-aware state machine over the existing direct Edge/CDP implementation.

Rejected alternatives:

- Generic recorded-action replay is too dependent on transient DOM paths and timing.
- PowerGate or desktop automation would attach behavior to a process LVMS-STAT does not own and would depend on window coordinates.
- Direct API or cookie replay would cross the approved session boundary and is out of scope.

## Command Interface

Add a dedicated command:

```text
python -m lvms_stat run-batch \
  --config config.json \
  --jobs jobs.json \
  --job ordered_test \
  --job answered_test \
  --job extraction_test
```

The `--job` option is repeatable and preserves command-line order. This first increment requires exactly three distinct job keys. Each key must resolve to exactly one strict local job. Existing single-job and supervised commands remain available and unchanged.

No real job keys or report configuration are committed. `jobs.example.json` remains synthetic.

## Architecture

### 1. Owned visible browser session

The batch opens one visible Edge child through the existing owned-browser startup path. It uses the dedicated local profile and loopback-only CDP endpoint. It never attaches to or terminates an existing Edge or PowerGate process.

Normal SSO may occur visibly. Automation proceeds only when the final page origin equals `expected_origin`.

### 2. Frame-aware document model

Add a batch-only `DocumentControlIdentity` that wraps the existing `ControlIdentity` with one bounded `frame` field:

- `top` identifies the top document;
- a non-empty frame name identifies one same-origin `iframe` or `frame` by exact sanitized `id` or `name`;
- URLs, frame sources, execution-context IDs, and cross-origin frame content are never stored or displayed.

Control discovery searches the top document and accessible same-origin child frames. It returns structural identity only. Every action resolves the identity again and requires exactly one visible, enabled, compatible control in the named document.

Existing workflow and stored report-contract schemas remain unchanged. The new wrapper is resolved at runtime and is not persisted in this increment, so no migration of locally stored recorder data or opaque contracts is required.

The implementation does not read form values, tables, grids, report output, or arbitrary frame text.

### 3. Automatic navigation state machine

The navigator starts at the configured `/clims` landing page and performs only allowlisted navigation actions:

1. Validate the expected origin.
2. If the Defined Reports page contract is already present, accept it.
3. Otherwise locate an exact safe navigation anchor for Defined Reports in the top document.
4. If it is not yet present, activate the exact safe section anchor, wait for the next state, then activate the Defined Reports anchor.
5. Validate the expected origin after every navigation action.
6. Accept the page only when all of these exist simultaneously:
   - top `SELECT#jobtypeselector[name=jobtypeselector]`;
   - `_nav_frame1` `BUTTON#clear[name=menu][type=button]`;
   - `_nav_frame1` `BUTTON#export[name=menu][type=button]`.

Text-based anchors are navigation fallbacks only. They cannot establish page identity by themselves. Exact labels are bounded, allowlisted UI metadata and are never derived from arbitrary page content.

All waits are condition-based and bounded. There are no fixed multi-second sleeps.

### 4. Staged report-form resolution

The form is dynamic, so fields are resolved only when their stage is active:

1. Resolve `report_type` from the stable top `jobtypeselector`.
2. Select the job's exact report type and wait for one category control.
3. Select the exact category and wait for one report-ID control.
4. Select the exact report ID and wait for the parameter controls.
5. Resolve exactly one analysis-code input, From-date input, and To-date input across the top document and same-origin named frames.
6. Populate the analysis list and explicit dates without reading existing values.
7. Revalidate origin, page contract, and export control before export.

Dynamic controls are found through narrow structural metadata and exact safe field-label aliases. A role must resolve to exactly one role-compatible control. Missing or multiple matches stop the batch.

LVMS may use ordinary HTML tables for form layout. A control inside such a layout table is eligible only when its own native/ARIA label or one narrow preceding label cell exactly matches an allowlisted field alias. Controls inside semantic grids/treegrids or any patient-, sample-, or result-marked ancestor are excluded. No table rows, cell values, or report data are returned.

Native selectors require exactly one option-text match. Custom selectors are focused, replaced through CDP input, and confirmed with Enter. No fuzzy or partial option match is allowed.

### 5. Batch orchestrator

The orchestrator loads and validates all three jobs before opening Edge. It rejects duplicate keys, duplicate output targets, invalid intervals, or any job that does not satisfy the strict schema.

For each job in order:

1. Revalidate origin and Defined Reports page contract.
2. Activate `clear` before the first field action, including for the first job, and wait for the base form state.
3. Populate the staged form.
4. Print only job key, report ID, analysis count, and explicit interval.
5. Start a fresh download baseline in the dedicated inbox.
6. Activate `export` automatically.
7. Wait up to the configured bounded report timeout for exactly one stable CSV and no unexpected file.
8. Finalize the file name.
9. Revalidate the page before continuing to the next job.

The batch stops on the first failure. It never blindly retries an export, because a retry could create a duplicate report.

Closing Edge or pressing Ctrl+C cancels the current batch and closes only the owned resources.

### 6. Download finalization

The dedicated Local AppData inbox is mandatory. The detector snapshots every file before each export and fails if it observes:

- more than one new file;
- a new non-CSV file;
- a lingering partial download;
- a completed file that disappears;
- a timeout.

The completed CSV is never opened, decoded, hashed, previewed, or parsed.

The destination name is:

```text
<output_stem>__<YYYY-MM-DD>__<YYYY-MM-DD>.csv
```

The first date is From and the second is To. The existing strict `output_stem` validation prevents path separators and unsafe names.

Finalization is an atomic move within the same dedicated inbox. If the destination already exists, the batch stops without overwriting, deleting, suffixing, or modifying either file. The newly downloaded original remains local for manual resolution.

### 7. Sanitized status model

Allowed status data:

- fixed state/category messages;
- job key;
- report ID;
- number of analysis codes;
- explicit From/To dates;
- success/failure per job;
- final safe filename, but not its absolute path.

Forbidden output:

- analysis-code list;
- field values read from LVMS;
- page/frame contents;
- absolute local paths;
- real hostname or navigation URLs;
- cookies, tokens, headers, storage, request/response bodies, or CDP payloads;
- CSV content or patient/sample/result data.

Exceptions retain internal chaining in memory but are converted to bounded categories at the CLI boundary.

## Error Handling and Stop Conditions

The entire batch fails closed when any of these occurs:

- configuration or job validation failure;
- owned Edge/CDP startup failure;
- SSO timeout or unexpected origin;
- missing, duplicated, hidden, disabled, read-only, incompatible, or cross-origin control;
- page contract mismatch;
- exact selector option not found;
- form state does not advance within its deadline;
- unexpected, ambiguous, partial, missing, or late download;
- destination filename already exists;
- connection or Edge cleanup failure.

The command returns:

- `0` only when all three files are finalized successfully;
- `2` for a bounded operational or integrity failure;
- `130` for operator cancellation.

Files successfully finalized before a later failure remain untouched. The status identifies the failed job key without exposing its analysis list or report contents.

## Local Job Configuration

The first work-computer batch uses exactly three local jobs and short explicit dates. The jobs represent the three previously defined Hemato statistics reports, but their real report IDs, analysis lists, and dates are not committed.

Each job keeps the existing strict fields:

- `job_key`;
- `report_type`;
- `category`;
- `report_id`;
- `analysis_codes`;
- `created_from`;
- `created_to`;
- `output_stem`.

Relative dates such as `-0` are not accepted in this increment.

## Testing Strategy

### Unit tests

- frame name sanitization and batch identity validation;
- same-origin frame traversal and cross-origin skipping;
- exact structural page contract;
- both allowlisted navigation routes;
- condition-based state transitions;
- role-compatible staged field resolution;
- native and custom selector behavior;
- exact three-job validation and ordering;
- deterministic filename generation;
- duplicate-target refusal and atomic move;
- sanitized messages and exit codes.

### Synthetic integration test

An in-process synthetic LVMS page contains:

- the landing navigation controls;
- a top `jobtypeselector`;
- a named same-origin frame with `clear` and `export`;
- category, report-ID, and parameter controls that appear dynamically;
- three synthetic report jobs;
- a synthetic download created only on export.

The test proves automatic navigation, frame resolution, staged population, three sequential exports, stable CSV detection, deterministic rename, and cleanup. It raises if production code tries to open or read a CSV. The default suite launches no browser and uses no network.

Adversarial tests cover ambiguous frames/controls, unexpected origin, duplicate destination, unexpected extra file, partial download, second-job failure, and cleanup failure.

### Work-computer acceptance

1. Pull the reviewed branch into Python Felles.
2. Use ignored local configuration and three jobs with short explicit dates.
3. Ensure the dedicated inbox and all deterministic destination names are absent.
4. Start `run-batch` once.
5. Observe one visible owned Edge session without interacting with it.
6. Require three fixed success statuses and three deterministically named CSV files.
7. Do not open the files.
8. Confirm Edge cleanup and a clean Git worktree.

Any origin, selector, file-count, duplicate, privacy, or cleanup failure ends the acceptance run. The operator reports only the fixed category and job key.

## Future Increments

After this batch succeeds repeatedly on the work computer:

1. add a PyQt6 interface as a thin client over the tested batch service;
2. add approved daily/weekly relative-date policies;
3. design historical backfill and metadata-based run ledger;
4. separately design identifier removal, aggregation, deduplication, and Power BI output.

None of these future increments are implicitly authorized by this design.
