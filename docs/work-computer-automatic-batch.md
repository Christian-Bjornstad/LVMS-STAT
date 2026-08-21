# Automatic three-report work-computer acceptance

This runbook validates one bounded capability: LVMS-STAT opens one visible, owned Edge session, navigates to Defined Reports, runs exactly three explicit short-date jobs, and finalizes exactly three CSV files. It never opens or reads the CSV content.

Run this only on the organisation-controlled work computer through the approved Python FELLES environment and normal authorised LVMS access. The `run-batch` invocation authorizes all three exports. There is no `EXPORT` confirmation, and a failed run must not be retried blindly.

## Preconditions

- Pull the reviewed implementation branch into the local repository.
- Copy `config.example.json` and `jobs.example.json` to the ignored `config.json` and `jobs.json` if local files do not already exist.
- Keep the real landing origin, report IDs, analysis codes, dates, directories, browser profile, and downloaded files only in ignored local files.
- Use the stable `/clims` landing path and one dedicated download inbox beneath Local AppData.
- Configure exactly three distinct jobs with short explicit `DD.MM.YYYY` From/To dates and distinct safe `output_stem` values.
- Do not use relative values such as `-0` in this acceptance run.

Verify the local files are ignored before continuing:

```powershell
git check-ignore config.json jobs.json
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
```

Both filenames must be reported. Stop if either is not ignored.

## Acceptance order

1. In the approved Python FELLES shell, update the reviewed branch and confirm `git status --short` contains no local report data.

2. Run the fixed capability check:

   ```powershell
   python -m lvms_stat doctor --config config.json
   ```

   Continue only after the exact result `LVMS CDP capability: ready.` The owned Edge window must close after the check.

3. Review the ignored `jobs.json` locally. It must contain exactly the three intended job keys, short explicit dates, and three distinct output stems. Do not print or copy the analysis lists.

4. Derive the expected names locally using this format and verify that none already exists in the dedicated inbox:

   ```text
   <output_stem>__<YYYY-MM-DD>__<YYYY-MM-DD>.csv
   ```

   Remove nothing automatically. If a destination already exists, stop and resolve it manually before a future run.

5. Invoke the batch once, preserving the intended job order:

   ```powershell
   python -m lvms_stat run-batch --config config.json --jobs jobs.json --job ordered --job answered --job extraction
   ```

   Replace the three synthetic example keys with the exact keys from the ignored local file. Do not add a contract argument; the batch resolves the validated live structure itself.

6. Leave the visible LVMS-STAT-owned Edge window alone. Normal SSO may be visible. Do not click, type, refresh, close, or navigate in that window while the command runs.

7. Require three fixed completion statuses and exactly the three expected filenames. A success status may show only job key, report ID, analysis count, explicit interval, and safe final filename. It must not show the analysis list, absolute path, page content, or report content.

8. Do not open, preview, parse, hash, upload, or copy any CSV during this acceptance run. Confirm only that the three filenames exist and no `.crdownload` or `.partial` file remains.

9. Confirm the owned Edge window and DevTools connection closed, then run:

   ```powershell
   git status --short
   ```

   No configuration, job, browser-profile, log, or report artifact may be staged or tracked.

10. If any step fails, report only the fixed failure category and safe job key. Do not share URLs, hostnames, paths, screenshots, analysis lists, cookies, headers, tokens, requests, responses, or CSV content.

## Stop rules

Stop immediately after an unexpected origin, missing or ambiguous control, unavailable exact option, download timeout, partial/unexpected/multiple file, existing destination, cancellation, or incomplete cleanup. Successfully finalized earlier files remain untouched. Never rerun an export merely because the status is uncertain; manual review comes first.

Direct managed Edge with loopback CDP is the only batch route in this increment. LVMS-STAT does not attach to PowerGate or an existing browser and does not replay APIs, cookies, or sessions.

## Explicitly outside this gate

This acceptance does not include PyQt6, Tkinter changes, cron or other scheduling, relative dates, historical backfill, CSV parsing, identifier removal, aggregation, deduplication by report content, Power BI refresh, or headless execution. Each requires a later, separately reviewed increment after this visible three-job batch is stable.
