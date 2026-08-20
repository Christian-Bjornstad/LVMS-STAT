# LVMS-STAT

LVMS-STAT is a supervised Python tool for exploring an approved, privacy-safe path from LVMS defined reports to aggregate statistics.

The current release is intentionally limited to an Edge connectivity probe and a sanitized control inspector. It does **not** run reports, download CSV files, process patient identifiers, schedule background work, or publish data to Power BI.

## Safety boundary

- Run the tool only on the organisation-controlled work computer.
- Use only your normal authorised LVMS access.
- Never copy cookies, authentication headers, cURL, HAR files, patient data, report files, screenshots, or the Edge profile into Git, GitHub, email, or an AI conversation.
- The inspector omits input values, password and hidden controls, table/grid controls, URLs, browser storage, cookies, and network data.
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

## Planned increments

1. Validate the supervised Edge/LVMS connection.
2. Map stable Defined Reports controls using sanitized metadata.
3. Automate one narrowly scoped report export through normal UI controls.
4. Validate and aggregate a synthetic CSV before processing any real report.
5. Produce an identifier-free Power BI input file in an approved location.

Every increment receives separate tests and review. API/cookie replay and headless personal-session automation are out of scope.
