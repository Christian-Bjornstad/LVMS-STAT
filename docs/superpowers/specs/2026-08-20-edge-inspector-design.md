# LVMS-STAT Edge Connectivity and Inspector Design

## Purpose

Prove that approved Python can launch the organisation-managed Microsoft Edge browser, reach the internal LVMS landing page through normal SSO, and inspect fixed user-interface controls without collecting patient data, session credentials, request headers, or report contents.

This is the first risk-reduction slice of a future LVMS-to-Power-BI pipeline. It does not execute reports, download files, process patient identifiers, schedule unattended work, or publish data.

## Recommended Architecture

LVMS-STAT launches a new, visible Edge process with a dedicated persistent profile and a randomly selected debugging port bound only to `127.0.0.1`. Python discovers the browser's DevTools endpoint through its loopback HTTP interface and sends narrowly scoped Chrome DevTools Protocol commands over a local WebSocket.

The dedicated profile is stored outside the repository in the current user's local application-data directory. It may contain authenticated session material and is therefore treated as a secret-bearing runtime directory. The program never reads, prints, exports, or serializes browser cookies.

The probe navigates only to a locally configured HTTPS LVMS origin. It reports a minimal result: whether Edge launched, whether the DevTools endpoint became available, the final origin, and the page title. It must not print a full URL because query strings can contain identifiers.

The inspector evaluates a fixed JavaScript expression that enumerates only fixed interactive-control metadata:

- element tag;
- `id`;
- `name`;
- `type`;
- `role`;
- `aria-label`;
- associated label text;
- short visible control text.

It excludes all form values, table cells, free text outside controls, cookies, storage, URLs, network headers, response bodies, and download links. Output is capped by control count and string length. Password controls are omitted entirely. Hidden controls are omitted by default.

## Components

### Configuration

`config.json` is created manually on the work computer and is ignored by Git. It contains only the LVMS landing URL and optional non-secret runtime paths. No username, password, cookie, token, patient identifier, internal report filename, or copied request is accepted.

Configuration validation requires:

- an `https` URL;
- no embedded credentials;
- no query string or fragment;
- a non-empty hostname;
- a profile directory outside the Git repository.

### Edge launcher

The launcher finds the installed `msedge.exe`, reserves an ephemeral loopback port, and starts Edge visibly with:

- `--remote-debugging-address=127.0.0.1`;
- the selected `--remote-debugging-port`;
- a dedicated `--user-data-dir`;
- a new window;
- no headless mode.

If organisational policy disables remote debugging, Edge exits, or the endpoint does not become ready within the timeout, the probe stops with a clear non-sensitive message. It never changes Edge policy or registry settings.

### DevTools connection

The client reads `/json/list` from loopback, chooses the page created by this Edge process, and connects to its advertised local WebSocket. Commands are limited to page navigation, document readiness, title/origin inspection, fixed control inspection, and clean browser shutdown.

The first slice uses the small `websocket-client` Python dependency because Python 3.11 does not include a synchronous WebSocket client. No Selenium, Playwright, Node.js, browser extension, or separate WebDriver executable is required.

### Safe inspector

The inspector is fail-closed. It validates the returned JSON shape, discards unknown fields, removes empty entries, truncates every string, limits the number of controls, and rejects any object containing a `value`, `href`, `src`, `cookie`, `token`, or `authorization` field.

Results are printed to the console only. The first slice does not write inspection output to disk.

## Security and Privacy Boundaries

- The tool runs only on the OUS-controlled work computer.
- The repository contains synthetic tests only.
- Real LVMS output, patient identifiers, session data, screenshots, HAR files, copied cURL, and complete internal URLs must never enter Git or this Codex task.
- The remote-debugging listener is loopback-only and uses an ephemeral port.
- The authenticated Edge profile is outside the repository and ignored defensively.
- The tool does not access browser cookie, storage, or network-interception CDP domains.
- The inspector does not read input values or page data tables.
- Logs contain no patient, sample, user, session, or report data.
- A failed page identity check stops all further interaction.
- No change is made to Edge or Ivanti policy. A blocked policy is reported as a hard stop.

## Error Handling

Errors are grouped into non-sensitive categories: configuration invalid, Edge not found, remote debugging blocked/unavailable, navigation timeout, unexpected origin, inspector response invalid, and browser shutdown failure. Raw exception strings from LVMS pages or WebSocket payloads are not printed by default.

The process returns a non-zero exit code on every failure. Browser cleanup is attempted in a `finally` block.

## Testing Strategy

Unit tests use synthetic HTML/control dictionaries and injected fake process/HTTP/CDP boundaries. Tests verify URL restrictions, argument construction, field allowlisting, truncation, password omission, forbidden-field rejection, and origin-only reporting. No test contacts LVMS or launches Edge.

The only work-computer integration check is manual and harmless: launch the dedicated Edge profile, navigate to the configured landing page, confirm the expected origin and title, inspect controls on a page containing no patient table, then close Edge.

## Initial Deliverable

- Local Git repository named `LVMS-STAT`.
- Python package and command-line entry point.
- Local configuration example with a non-routable placeholder hostname.
- Tested configuration validator.
- Tested Edge argument builder and process lifecycle.
- Tested safe-control sanitizer and synthetic inspector fixture.
- Work-computer runbook for the connectivity/inspection probe.

## Explicitly Not Included

- Report selection or execution.
- CSV download automation.
- Patient-data processing or Power BI output.
- API/cookie/request replay.
- Credential storage.
- Screenshots or video capture.
- Background, headless, scheduled, or unattended operation.
- GitHub publication or deployment.

Those capabilities require separate reviewed increments after this probe succeeds and after the data-processing location and retention rules are approved.
