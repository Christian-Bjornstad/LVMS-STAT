# LVMS-STAT

LVMS-STAT is a supervised Python tool for exploring an approved, privacy-safe path from LVMS defined reports to aggregate statistics.

The current development release adds a local Tkinter recorder for one supervised Defined Reports workflow. It records only sanitized control actions, detects a new CSV without reading it, and can ask Windows to open that file locally. It does **not** replay workflows, process patient identifiers, schedule background work, or publish data to Power BI.

## Safety boundary

- Run the tool only on the organisation-controlled work computer.
- Use only your normal authorised LVMS access.
- Never copy cookies, authentication headers, cURL, HAR files, patient data, report files, screenshots, or the Edge profile into Git, GitHub, email, or an AI conversation.
- The inspector omits input values, password and hidden controls, table/grid controls, URLs, browser storage, cookies, and network data.
- The recorder never reads typed values or CSV contents and does not display filenames or paths.
- Edge remains visible and uses a dedicated profile outside this repository.
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
3. Validate stable selectors, then automate one narrowly scoped report export through normal UI controls.
4. Validate and aggregate a synthetic CSV before processing any real report.
5. Produce an identifier-free Power BI input file in an approved location.

Every increment receives separate tests and review. API/cookie replay and headless personal-session automation are out of scope.
