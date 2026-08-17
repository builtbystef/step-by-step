---
id: 94xanm
title: Extension distribution and the connect flow
state: todo
priority: medium
depends_on:
    - lac27w
parent: d8ux2s
created: 2026-08-14T06:02:27Z
updated: 2026-08-17T04:04:21Z
---

## What to build

The MV3 extension package and the path from a fresh browser to a connected instance. v1 ships unpacked: the backend serves its own paired build as a zip, beside an install page (unzip → the extensions page → Developer mode → Load unpacked), and the install docs note in one sentence that Windows/macOS fleets can force-install via enterprise policy — nothing is built for it. Because `externally_connectable` cannot express an arbitrary self-hosted origin, the extension opens the channel, never the app: the user enters the instance URL in the popup, grants that one origin, and the extension injects its content script into the app's connect page for a nonce-checked handshake. The workspace check and test commands cover the new package.

## Acceptance criteria

- [ ] The extension is a plain MV3 package (no framework) whose manifest pins a key (stable ID regardless of install directory), declares minimum Chrome 118, and requests broad host access only as optional permissions.
- [ ] The backend serves the paired build as a zip download beside an install page describing the unpacked sequence; the docs carry the one-sentence enterprise-policy note.
- [ ] Connect, once per instance, from the popup: entering the instance URL requests permission for that origin from a user gesture; on grant the extension opens the app's connect page there and receives the handshake via postMessage — accepted only from the connected origin and only when it matches a nonce the extension generated for that attempt.
- [ ] When the grant flow is declined, the app can display a one-time connect code that the user pastes into the popup and the extension exchanges at the backend; the one granted origin covers both content-script injection and the service worker's fetch.
- [ ] An unauthenticated version endpoint reports the current and minimum-supported extension versions.
- [ ] Every message the extension accepts is validated — origin, sender, tab context, payload — with content-script messages doubly so.
- [ ] The extension test harness exists: Playwright driving headless Chromium with the unpacked build, proving the package loads and the handshake validation rejects a wrong-origin or wrong-nonce message.

## Notes

**claude** — 2026-08-17T04:04:21Z

Pinned connect-code fallback (this slice owns it): authenticated POST /api/extension/connect-codes → 201 {code, expires_at} — single-use, 10-minute TTL, displayed by the app's connect surface; unauthenticated POST /api/extension/connect {code} → 200 {} consuming the code, 401 bad_code otherwise. Success tells the extension the entered origin is a live instance whose signed-in user authorized pairing; the extension then stores the origin as connected. The zip and install page are unauthenticated, like the version endpoint. Attended-verification plan (loop operator's decision): the popup's permission-grant gesture cannot be driven headlessly — build everything including the Playwright harness ACs, then apply needs-review with a note naming the gesture-dependent checks for a manual pass in real Chrome, and do not close.
