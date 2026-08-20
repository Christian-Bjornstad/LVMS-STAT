# Work-computer workflow recorder

This runbook records and reviews one authorised LVMS Defined Reports workflow. It never reads typed field values or CSV contents. Run it only on the organisation-controlled work computer after the connectivity probe succeeds.

## 1. Confirm the local UI is available

From PowerShell:

```powershell
python -c "import tkinter; print(tkinter.TkVersion)"
```

If this fails, stop and request an approved Python installation with Tkinter. Do not install an unapproved runtime or package an executable.

## 2. Complete the ignored local configuration

Ensure `config.json` contains the clean HTTPS landing URL and three absolute local directories:

- the dedicated Edge profile beneath Local AppData;
- the normal approved CSV download directory; and
- workflow storage beneath Local AppData.

All must be outside this repository. Do not add credentials, cookies, identifiers, copied requests, report filenames, or download URLs.

Confirm that Git ignores the configuration:

```powershell
git check-ignore config.json
```

Expected output: `config.json`.

## 3. Launch the recorder

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m lvms_stat app --config config.json
```

The app opens as a separate local window. Enter a short workflow name and notes that contain no patient, sample, employee, internal host, or session information.

## 4. Record one report workflow

1. Press **Start recording** and accept the privacy confirmation.
2. Use the new visible Edge window and complete normal SSO if requested. SSO actions are not recorded.
3. Navigate to the authorised Defined Reports workflow.
4. Enter the From and To dates normally. The review must show only that each field was edited, followed by `[value not recorded]`.
5. Complete the remaining safe menu/button interactions.
6. Click Export and let LVMS create its normal CSV.
7. Press **Stop** if the app has not already detected the completed download.

Stop immediately if an unexpected origin, patient/results table, or sensitive control text appears in the recorder review.

## 5. Review and save sanitized steps

Read every displayed step locally. The review may contain only numbered clicks, selections, edited-field identities, parameter roles, and Download detected.

Assign `from_date` and `to_date` to the corresponding edited fields. The `other_parameter` role is available for another safe field identity, but version 1 stores no parameter values.

Use **Save review** only after checking every step. The saved JSON remains beneath Local AppData. Do not upload or share it, even though the app applies a strict sanitized schema.

## 6. Confirm the CSV locally

- If one stable new CSV is detected, **Open CSV locally** asks Windows to open the exact file in the approved default application.
- If no CSV is detected, verify the normal download locally; the recorded review remains available.
- If multiple CSV files are detected, the app refuses to guess. Resolve the ambiguity locally and repeat the recording if needed.

The app does not parse, preview, hash, copy, or upload the CSV. Opening it does not approve any other handling or storage location.

## 7. Close and retain nothing unintended

Close the app and its tracked Edge child. Confirm that the repository remains clean:

```powershell
git status --short
```

Never commit, upload, email, or paste:

- `config.json`;
- workflow JSON;
- the Edge profile;
- CSV/XLSX/PDF report files;
- screenshots or video;
- copied DevTools requests, cURL, fetch, or HAR data;
- cookies, tokens, headers, internal URLs, or diagnostics; or
- patient, sample, result, or employee information.

Version 1 records and reviews only. It does not replay the steps, schedule reports, process the CSV, or feed Power BI.
