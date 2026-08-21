# Supervised LVMS report test on the work computer

This runbook proves one narrow capability: Python FELLES starts an owned, visible Edge window, reaches the configured LVMS origin through normal SSO, identifies the Defined Reports form, fills one locally configured job, and detects one completed CSV. It does not read or open the CSV.

Use only the organisation-controlled work computer and your normal authorised access. Stop immediately if a patient/sample table, unexpected origin, ambiguous selector, multiple download, or cleanup failure appears.

## Local preparation

Copy `config.example.json` to the ignored `config.json` and `jobs.example.json` to the ignored `jobs.json`. Replace only the placeholders locally. Use a clean HTTPS landing URL without credentials, query string, fragment, session data, or a generated download URL. All local directories must be absolute and outside the repository.

Before continuing:

```powershell
git check-ignore config.json jobs.json
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
```

Both local JSON filenames must be reported as ignored. Never commit the local configuration, job, contract, Edge profile, or report files.

## Ordered gates

### Gate 0 — start manually in Python FELLES

Open the approved Python FELLES environment through the normal Ivanti route, open its approved command shell, change to this repository, and set `PYTHONPATH` as shown above. Do not build or run an executable.

### Gate 1 — fixed capability check

```powershell
python -m lvms_stat doctor --config config.json
```

Continue only after the exact result:

```text
LVMS CDP capability: ready.
```

The owned Edge window must close when the command finishes. Any other result is a stop.

### Gate 2 — discover the report form

```powershell
python -m lvms_stat discover-report --config config.json
```

In the Edge window, navigate to **Eksterne rapporter → Definerte rapporter**. Keep the page free of patient/sample tables and generated report output. Return to the console and type the exact word `DISCOVER`.

Expected fixed result:

```text
Report contract saved locally.
```

This gate never selects or exports a report.

### Gate 3 — retain the opaque contract locally

Confirm that exactly one new randomly named `.json` file exists in the configured `contract_directory`. Do not rename, edit, display in screenshots, paste, upload, or commit it. If no file or more than one candidate exists, stop and resolve the local ambiguity before continuing.

### Gate 4 — populate one reviewed job

Use the one local `job_key` and the absolute path to that new contract:

```powershell
python -m lvms_stat run-job --config config.json --jobs jobs.json --contract "C:\absolute\local\contracts\opaque.json" --job synthetic_ordered
```

The visible review may contain only job key, report ID, analysis count, and From/To dates. It must not print the analysis list or report contents. Verify all four items locally.

### Gate 5 — permit one export

Type the exact word `EXPORT` once. Any other input cancels without pressing the export control. Stop if the origin changes unexpectedly, a selector is missing/ambiguous, multiple files appear, the wait exceeds ten minutes, or browser cleanup fails.

Expected success result:

```text
Report download: one completed CSV detected.
```

### Gate 6 — confirm locally, without opening

Confirm in File Explorer that one completed `.csv` exists in `download_directory` and no partial download remains. Do not open, preview, parse, copy, upload, or commit the file during this integration subproject.

## Capability troubleshooting

| Result code | One permitted action |
|---|---|
| `ready` | Continue to Gate 2. |
| `config_invalid` | Correct only the ignored local paths/clean landing URL. |
| `edge_unavailable` | Stop and ask IT whether managed Edge launch is available to Python FELLES. |
| `cdp_unavailable` | Stop and ask IT whether approved local Edge debugging is permitted. |
| `unexpected_origin` | Stop; verify only the clean configured landing origin locally. |
| `protocol_invalid` | Stop and retain only the fixed category message for troubleshooting. |
| `cleanup_incomplete` | Close the LVMS-STAT-owned Edge window manually, then stop. |

Do not change Edge policy, registry, Ivanti settings, authentication material, or application-control settings. Do not collect DevTools traffic, copied requests, HAR files, cookies, headers, session values, screenshots, or report content for troubleshooting.

## Pass criteria

The test passes only if every gate passes in order, one CSV is detected, its content remains unread, the owned Edge window closes, and `git status --short` shows no local data staged or tracked. A failed gate is not permission to bypass or retry blindly.
