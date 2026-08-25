---
id: 7vuup5
title: 'Recording end to end: starting from the app, the save screen, and surviving death'
state: in-progress
priority: medium
labels:
    - needs-review
depends_on:
    - bysmhd
    - rjklmp
    - y2fsy1
    - 56r40g
    - 0zwbku
parent: d8ux2s
created: 2026-08-14T06:03:37Z
updated: 2026-08-25T13:33:00Z
---

## What to build

The full recording loop, closed. The editor starts a recording: the app mints a session and hands the session id, token, backend origin, workflow name, and mode to the extension through the connected origin's content script. The extension records, checkpoints directly to the backend (never through the app tab), and ends with a save screen. The service worker stays a restartable coordinator — recording id, tab id, attachment state, and buffered-step checkpoints persist after each event, surviving the 30-second idle kill. Re-recording a Draft that already has Steps replaces them, behind a confirm in the app before the session starts.

## Acceptance criteria

- [ ] Start recording from the editor mints a session and reaches the extension via the postMessage handshake; on a Draft that already has Steps, a confirm in the app precedes the session, and finalizing replaces them.
- [ ] The save screen lists every needs-secret Step and refuses to finalize until each is bound to a new or existing secret Variable, landing as a `{{name}}` reference; discard drops the recording; the backend's rejection of an unresolved marker is unreachable through this flow.
- [ ] Killing the service worker mid-recording (the 30 s idle kill) loses nothing: state and buffered checkpoints persist, and the finished recording contains every Step captured before and after the kill.
- [ ] Token expiry mid-recording: the app re-mints against the same session, the extension resumes, and buffered Steps survive locally and on the server.
- [ ] Closing the app tab during a recording costs nothing — checkpoints go directly to the backend.
- [ ] End to end on a fixture site: record clicks and typing, bind the password Step to a secret Variable, save — the editor then shows the finished Steps in the Draft.

## Notes

**claude** — 2026-08-17T04:04:21Z

Attended-verification plan (loop operator's decision): cover checkpointing, service-worker-kill persistence, and app-tab-close survival in the harness where it can drive them; any AC the harness cannot drive goes into a needs-review note for the user's attended pass instead of closing unverified.

**agent** — 2026-08-24T09:35:35Z

Implementation is blocked by an undecided Chrome permission boundary. The app-first start must inject recorder-content.js into an arbitrary target site, but the connect flow grants only the instance origin and chrome.scripting.executeScript requires either target-origin host permission or activeTab. Chrome permits requesting optional host access only from an extension user gesture, so the editor's Start recording click cannot grant it. Options: (1) require a second click in the extension popup to grant the target origin and start, changing the app-first flow; (2) redesign capture to operate entirely through chrome.debugger/CDP without content-script injection; or (3) require broad target-site access at install/policy time. User must decide, record the decision in a note (and the parent spec/architecture), and remove needs-review.

**agent** — 2026-08-24T10:12:17Z

Decision approved by the user: use extension-popup confirmation. Start recording in the editor creates a pending session; the user opens the intended target tab and confirms in the extension popup. That popup gesture requests the target origin when needed, then starts only after the grant. Remembered per-origin grants skip Chrome's permission dialog but not the per-recording popup confirmation. Declining leaves the session pending and injects nothing. Do not use CDP-only capture or broad install-time host access. The parent spec and architecture now record this boundary.

**agent** — 2026-08-24T16:50:37Z

Implemented the full recording loop. The editor now confirms replacement before minting, hands pending sessions to the connected extension, rotates an expired token against the same session, and refreshes the Draft after finalization. The popup owns target-tab confirmation and optional host permission, recording stop/review, password-Step binding to existing or new secret Variables, save, and discard. The service worker persists pending/active/ended state and full Step buffers in local storage, checkpoints and finalizes directly to the backend, retries the full checkpoint after token rotation, and announces expiry/finalization to app tabs. Automated coverage now exercises app-to-extension pending handoff, direct checkpoint/finalize, password binding with no literal leakage, and the existing recorder pipeline; pnpm check, pnpm test, and pnpm test:browser pass.

Attended review is still required by the issue's verification plan: in real Chrome, verify the native target-origin permission grant/decline; replace a non-empty Draft and confirm the finished click/type/password recording appears in the editor; close the app tab during capture; force a service-worker stop and continue capture if Chrome permits that while debugger is attached; and exercise the expired-token resume path. Close to approve, or note requested changes and remove needs-review.

**agent** — 2026-08-25T12:37:45Z

Attended Test B found that the popup could not identify an ungranted target tab: without activeTab, chrome.tabs.query returned no URL before the optional host permission could be requested. Fixing this under the same acceptance criterion.

**agent** — 2026-08-25T12:38:47Z

Fixed the attended Test B failure by adding activeTab to the extension manifest. Invoking the toolbar action now gives the popup enough temporary access to read the current tab URL, after which the existing explicit optional-host permission request still controls whether recording may start. Added a manifest contract test and documented the boundary. All checks and browser tests pass. User must reload the unpacked extension on chrome://extensions and rerun Test B; the remaining attended checks still apply.

**agent** — 2026-08-25T13:29:34Z

Attended Test C found the recorder content script crashed on an insecure HTTP origin because crypto.randomUUID is secure-context-only. Replacing that page-load id source with getRandomValues and adding insecure-origin browser coverage.

**agent** — 2026-08-25T13:33:00Z

Fixed Test C's insecure-origin crash. recorder-content.js now mints its page-load correlation id with crypto.getRandomValues, which remains available on ordinary HTTP pages, instead of secure-context-only crypto.randomUUID. Browser coverage now records a click through an actual http://0.0.0.0 fixture where randomUUID is absent. pnpm check, pnpm test, and pnpm test:browser pass. User must reload the unpacked extension and rerun Test C; remaining attended checks still apply.
