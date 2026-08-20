# Work-computer Edge probe

This runbook verifies only that Python can launch the managed Edge browser with a dedicated profile and reach the configured LVMS origin through normal SSO. It does not generate or download a report.

## 1. Confirm prerequisites

In Edge, open `edge://policy` and search for `RemoteDebuggingAllowed`.

- If it is `false` or disabled, stop and ask IT whether this supervised automation may be enabled.
- If it is `true`, enabled, or not listed, continue.
- Do not edit the registry, browser policy, Ivanti configuration, or Edge installation.

In PowerShell, check Python and the one runtime dependency:

```powershell
python --version
python -c "import websocket; print(websocket.__version__)"
```

Python must be 3.11 or newer. If `websocket` is unavailable, stop and request an approved installation route; do not download or install around application-control policy.

## 2. Create ignored local configuration

Copy `config.example.json` to `config.json`. The latter is excluded by `.gitignore`.

Edit only these two values locally:

- `landing_url`: the clean HTTPS LVMS landing page, with no query string or fragment.
- `profile_directory`: an absolute directory beneath your local application-data area and outside this repository.

Do not add usernames, passwords, tokens, cookies, patient identifiers, report paths, copied requests, or download URLs.

Confirm Git will not track the file:

```powershell
git check-ignore config.json
```

Expected output: `config.json`.

## 3. Run connectivity only

From PowerShell in the repository:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m lvms_stat probe --config config.json
```

Expected behaviour:

1. A new visible Edge window opens with a dedicated profile.
2. Edge navigates to the configured clean landing page.
3. Normal Windows/SSO authentication occurs. A first run may require a visible manual sign-in through the approved OUS flow.
4. The console prints only the final origin and a short page title.
5. Edge closes when the probe finishes.

Stop if the output reports that managed Edge is unavailable, the connection timed out, or an unexpected origin was reached. Share only that category message—not browser/profile files or diagnostic headers.

## 4. Run sanitized inspection

Use inspection only on a page with no patient, sample, result, or free-text table visible.

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m lvms_stat inspect --config config.json
```

When Edge opens:

1. Navigate manually to the non-patient Defined Reports menu.
2. Confirm that no patient/sample table or report result is visible.
3. Return to PowerShell and type the exact confirmation `INSPECT`.
4. The console prints line-oriented JSON containing only sanitized fixed-control metadata.

The output may include tag, ID, name, type, role, label, short text, and a non-URL frame name. It excludes form values, password and hidden controls, controls inside tables/grids, links/URLs, cookies, browser storage, request headers, and network bodies.

Before sharing any inspector output for development, read every line yourself and remove anything that could identify a patient, sample, employee, internal host, or session. If uncertain, do not share it.

## Never collect or share

- DevTools request headers or payloads.
- Cookies or SSO/session values.
- “Copy as cURL” or “Copy as fetch”.
- HAR exports.
- Screenshots or video containing LVMS content.
- The dedicated Edge profile directory.
- Generated CSV/XLSX/PDF files.
- Patient, sample, result, or report-level data.
