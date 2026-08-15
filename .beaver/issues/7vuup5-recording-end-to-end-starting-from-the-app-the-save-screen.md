---
id: 7vuup5
title: 'Recording end to end: starting from the app, the save screen, and surviving death'
state: todo
priority: medium
depends_on:
    - bysmhd
    - rjklmp
    - y2fsy1
parent: d8ux2s
created: 2026-08-14T06:03:37Z
updated: 2026-08-14T06:03:37Z
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
