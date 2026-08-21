# LVMS-STAT

LVMS-STAT is a Python tool for an approved, privacy-safe path from LVMS Defined Reports to locally downloaded statistics files.

The current development release provides a one-click PyQt6 app that runs exactly three explicit local report jobs automatically in one visible, tool-owned Edge session. It navigates through normal SSO and UI controls, fills each dynamic form, exports once, detects exactly one CSV, and gives it a deterministic non-overwriting name without opening or reading it. It does **not** process identifiers, schedule background work, aggregate reports, or publish data to Power BI.

## Safety boundary

- Run the tool only on the organisation-controlled work computer.
- Use only your normal authorised LVMS access.
- Never copy cookies, authentication headers, cURL, HAR files, patient data, report files, screenshots, or the Edge profile into Git, GitHub, email, or an AI conversation.
- The inspector omits input values, password and hidden controls, table/grid controls, URLs, browser storage, cookies, and network data.
- The one-click app never opens or reads CSV contents and does not display absolute paths.
- Edge remains visible and uses a dedicated profile outside this repository.
- `run-batch` is the authorization for all three exports; it has no confirmation prompt and stops after the first failure.
- Existing destination files are never overwritten or automatically suffixed.
- If organisational Edge policy blocks remote debugging, stop and ask IT; do not change policy or registry settings.

## Requirements

- Windows 10 or 11.
- Python 3.11 or newer.
- Organisation-managed Microsoft Edge.
- `websocket-client` 1.8 or newer, installed through an approved process.
- PyQt6 6.7 or newer, installed through an approved process.
- Edge policy `RemoteDebuggingAllowed` enabled or not configured.

## Development checks

From PowerShell in the repository:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -t . -v
python -m lvms_stat --help
```

The automated tests use synthetic values only and do not launch Edge or contact LVMS.

## Troubleshooting tools

The normal workflow uses the PyQt6 app below. `probe` and `inspect` remain available only for troubleshooting; use `inspect` only when the visible page contains no patient or sample table.

The existing [Archer-prosess](https://github.com/Christian-Bjornstad/Archer-prosess) project proves that direct managed Edge CDP can run in the approved Python FELLES environment. LVMS-specific SSO, origins, and selectors are still environment-dependent and must pass the supervised gates locally.

## One-click three-report app

Prepare ignored `config.json` and `jobs.json` in the repository root. The jobs file must contain `ordered`, `answered`, and `extraction`. Start the visible app directly; no separate doctor command is required:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m lvms_stat app --config config.json
```

Press **Kjør rapporter** once. The app opens visible Edge, reports progress from 1 to 3, and stops after success, cancellation, or the first failure. It never retries automatically. See [docs/work-computer-automatic-batch.md](docs/work-computer-automatic-batch.md) for the short work-computer procedure.

## Planned increments

1. Validate the supervised Edge/LVMS connection.
2. Record and review one Defined Reports workflow using sanitized metadata.
3. Automatically export exactly three explicit short-date jobs through normal visible UI controls.
4. Add a one-click PyQt6 client over the tested batch service. **Current.**
5. Add historical backfill and daily/weekly scheduling.
6. Validate identifier removal, aggregation, and duplicate handling before processing reports.
7. Produce an identifier-free Power BI input file in an approved location.

Every increment receives separate tests and review. API/cookie replay and headless personal-session automation are out of scope.
