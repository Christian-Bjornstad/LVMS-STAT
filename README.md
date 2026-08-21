# LVMS-STAT

LVMS-STAT is a Python tool for an approved, privacy-safe path from LVMS Defined Reports to locally downloaded statistics files.

The current development release can run exactly three explicit local report jobs automatically in one visible, tool-owned Edge session. It navigates through normal SSO and UI controls, fills each dynamic form, exports once, detects exactly one CSV, and gives it a deterministic non-overwriting name without opening or reading it. The earlier supervised discovery and single-job commands remain available. It does **not** process identifiers, schedule background work, aggregate reports, or publish data to Power BI.

## Safety boundary

- Run the tool only on the organisation-controlled work computer.
- Use only your normal authorised LVMS access.
- Never copy cookies, authentication headers, cURL, HAR files, patient data, report files, screenshots, or the Edge profile into Git, GitHub, email, or an AI conversation.
- The inspector omits input values, password and hidden controls, table/grid controls, URLs, browser storage, cookies, and network data.
- The recorder never reads typed values or CSV contents and does not display filenames or paths.
- Edge remains visible and uses a dedicated profile outside this repository.
- `run-batch` is the authorization for all three exports; it has no confirmation prompt and stops after the first failure.
- Existing destination files are never overwritten or automatically suffixed.
- If organisational Edge policy blocks remote debugging, stop and ask IT; do not change policy or registry settings.

## Requirements

- Windows 10 or 11.
- Python 3.11 or newer.
- Organisation-managed Microsoft Edge.
- `websocket-client` 1.8 or newer, installed through an approved process.
- Edge policy `RemoteDebuggingAllowed` enabled or not configured.

## Development checks

From PowerShell in the repository:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -t . -v
python -m lvms_stat --help
```

The automated tests use synthetic values only and do not launch Edge or contact LVMS.

## Work-computer probe

Follow [docs/work-computer-probe.md](docs/work-computer-probe.md). Begin with `probe`; use `inspect` only after confirming that the visible page contains no patient or sample table.

The existing [Archer-prosess](https://github.com/Christian-Bjornstad/Archer-prosess) project proves that direct managed Edge CDP can run in the approved Python FELLES environment. LVMS-specific SSO, origins, and selectors are still environment-dependent and must pass the supervised gates locally.

## Supervised report gates

Follow [docs/work-computer-cdp-integration.md](docs/work-computer-cdp-integration.md). Prepare ignored `config.json` and `jobs.json`, then run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m lvms_stat doctor --config config.json
python -m lvms_stat discover-report --config config.json
python -m lvms_stat run-job --config config.json --jobs jobs.json --contract "C:\absolute\local\contracts\opaque.json" --job synthetic_ordered
```

The first work-computer execution remains supervised. Stop after any origin, selector, download-count, cleanup, or privacy failure.

## Automatic three-report batch

Follow [docs/work-computer-automatic-batch.md](docs/work-computer-automatic-batch.md) only after `doctor` reports ready. Prepare exactly three ignored local jobs with short explicit dates and distinct output stems, then run:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m lvms_stat run-batch --config config.json --jobs jobs.json --job ordered --job answered --job extraction
```

The job keys above are synthetic examples; use the three keys from the ignored local `jobs.json`. Do not interact with the visible Edge window during the batch. Success requires three exact CSV filenames and successful owned-browser cleanup.

## Work-computer recorder

After the probe succeeds, follow [docs/work-computer-recorder.md](docs/work-computer-recorder.md). Launch it with:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m lvms_stat app --config config.json
```

Use a non-sensitive workflow name and notes. The app records and reviews one supervised workflow; it does not replay it.

## Planned increments

1. Validate the supervised Edge/LVMS connection.
2. Record and review one Defined Reports workflow using sanitized metadata.
3. Automatically export exactly three explicit short-date jobs through normal visible UI controls. **Current.**
4. Add a PyQt6 client over the tested batch service.
5. Design approved scheduling and historical backfill separately.
6. Validate identifier removal and aggregation before processing any real report.
7. Produce an identifier-free Power BI input file in an approved location.

Every increment receives separate tests and review. API/cookie replay and headless personal-session automation are out of scope.
