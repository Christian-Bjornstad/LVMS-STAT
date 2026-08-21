# Automatic three-report work-computer run

LVMS-STAT opens one visible Edge session, navigates to Defined Reports, runs three configured jobs, and finalizes three CSV files. It never opens or reads the CSV content.

Run this only on the organisation-controlled work computer through the approved Python FELLES environment and normal authorised LVMS access. The `run-batch` invocation authorizes all three exports. There is no `EXPORT` confirmation, and a failed run must not be retried blindly.

## Preconditions

- Pull the current implementation branch into the local repository.
- Keep ignored `config.json` and `jobs.json` in the repository root.
- Keep the real landing origin, report IDs, analysis codes, dates, directories, browser profile, and downloaded files only in ignored local files.
- Use the stable `/clims` landing path and one dedicated download inbox beneath Local AppData.
- Configure the job keys `ordered`, `answered`, and `extraction`, with explicit `DD.MM.YYYY` dates and distinct output stems.
- Do not use relative values such as `-0` in this acceptance run.

Verify the local files are ignored before continuing:

```powershell
git check-ignore config.json jobs.json
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
```

Both filenames must be reported. Stop if either is not ignored.

## Run

1. Start the app in the approved Python FELLES shell:

   ```powershell
   $env:PYTHONPATH = (Join-Path (Get-Location) 'src')
   python -m lvms_stat app --config config.json
   ```

2. Press **Kjør rapporter** once.
3. Leave the Edge window alone while the app shows report 1, 2, and 3.
4. A failure stops the run. Fix the cause before pressing the button again.

## Stop rules

The app stops after an unexpected page, missing or ambiguous control, invalid option, download timeout, incomplete download, existing destination, cancellation, or incomplete cleanup. Successfully finalized earlier files remain untouched.

Direct managed Edge with loopback CDP is the only batch route in this increment. LVMS-STAT does not attach to PowerGate or an existing browser and does not replay APIs, cookies, or sessions.

## Next increments

Scheduling, historical backfill, CSV processing, identifier removal, aggregation, deduplication, and Power BI refresh come after the visible three-job run works on the work computer.
