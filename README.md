# LVMS-STAT

LVMS-STAT is a small Windows/PyQt6 app that opens a visible Microsoft Edge session and downloads three configured LVMS Defined Reports:

1. `ordered`
2. `answered`
3. `extraction`

The app fills the report forms through Edge CDP, downloads each CSV, and gives it a deterministic name. It does not open or analyze the CSV content.

Start with [START_HER.md](START_HER.md). The next development stages are in [PLAN_VIDERE.md](PLAN_VIDERE.md).

## Main files

- `src/lvms_stat/` — PyQt6 app and Edge/CDP batch code.
- `LVMS-STAT_INSTALLER.cmd` — installs the app through Python FELLES.
- `LVMS-STAT_START.cmd` — opens the app through Python FELLES.
- `config.example.json` — template for the local browser and download configuration.
- `jobs.hematology-test.json` — the three approved hematology test jobs for
  01–07 August 2026.
- `jobs.example.json` — synthetic template for later custom report jobs.
- `tests/` — offline tests that do not contact LVMS or start Edge.

Local `config.json`, `jobs.json`, downloaded reports, browser profiles, and logs are ignored by Git.

## Development test

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest -q
```
