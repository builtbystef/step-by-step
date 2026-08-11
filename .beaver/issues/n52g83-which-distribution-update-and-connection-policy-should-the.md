---
id: n52g83
title: Which distribution, update, and connection policy should the v1 Chrome extension use?
state: done
assignee: claude
labels:
    - roadmap:idnzwf
    - session:grill
depends_on:
    - 1zg7o0
parent: idnzwf
created: 2026-08-10T02:26:59Z
updated: 2026-08-11T21:33:02Z
---

Choose v1 extension distribution and update policy now that 1zg7o0 settled the recorder/auth boundary.

Decide:
- Chrome Web Store publication, unpacked developer installation, or another supported distribution path for v1;
- whether self-hosted deployments use one shared extension build and the implications for stable extension ID;
- update channel and compatibility/minimum Chrome version (the recorder may require Chrome 118+ for debugger-session worker liveness);
- confirm the direct extension-to-backend handshake: the app initiates an allowlisted connection, backend mints a short-lived recording-scoped credential, extension calls backend directly.

Read the 1zg7o0 research note before the decision.

## Notes

**claude** — 2026-08-11T21:33:02Z

## Question

Which distribution, update, and connection policy should the v1 Chrome extension use?

## Answer

v1 ships the extension **unpacked**, served by the instance itself. No Chrome Web Store listing, no `.crx`/`update_url`, no auto-update. The manifest pins a `key` for a stable ID and declares `minimum_chrome_version: "118"`. The **extension opens the connection**, not the app: `externally_connectable` cannot name an arbitrary self-hosted origin, so the popup takes the instance URL, requests optional host permission for it, and receives the handshake through a content script on the app's connect page. The direct extension→backend model is confirmed unchanged: the backend mints the short-lived recording-scoped token and the extension calls checkpoint and finalize itself.

Spec `d8ux2s` has been amended: a new "Distribution, updates, and connection" subsection, a rewritten "Recording session protocol" (its `externally_connectable` handshake was unimplementable), a version-refusal test example, and four new Out of Scope lines.

## Decisions

### Distribution — unpacked, served by the instance

The backend serves the extension build paired with it at `GET /extension.zip`, with an install page (unzip → `chrome://extensions` → Developer mode → Load unpacked) linked from the app UI. Rejected: Chrome Web Store (deferred to the Frontier, not rejected on merit — it is the only path that installs cleanly on Windows/macOS and auto-updates, but it costs a developer account, review latency on every release, and permission justification for `debugger`); self-hosted `.crx` with an `update_url` (off-store `.crx` installs are Linux-only); a per-deployment build with the operator's origin compiled in (unnecessary once the extension opens the channel).

Accepted costs, eyes open: every user enables Developer mode; there is no auto-update; Chrome treats unpacked extensions as lower-trust and can disable them across updates or profile reloads. Windows/macOS fleets can force-install off-store through enterprise policy (`ExtensionInstallForcelist`) — one sentence in the install docs, nothing built.

### Connection — the extension opens the channel

**The hard constraint, and the reason this decision looks backwards:** `externally_connectable.matches` rejects wildcard domains and subdomains of effective TLDs — `<all_urls>`, `http://*/*`, and `*://*.com/*` are all invalid; a pattern needs a real second-level domain. A self-hoster's origin is unknown at build time, so one shared build can never be messaged by the app. The published spec assumed it could.

The flow, once per instance, in the extension popup: the user enters the instance URL → `chrome.permissions.request` for that origin from a user gesture (`optional_host_permissions: ["*://*/*"]`) → the extension opens the app's connect page there, injects its content script, and the page hands the handshake over `window.postMessage`, accepted only from the connected origin and only when it matches a nonce the extension generated for that attempt. That one grant covers both the injection and the service worker's `fetch`. Fallback when the grant is declined: the app displays a one-time connect code the user pastes into the popup, which the extension exchanges at the backend.

### Direct extension→backend calls — confirmed

Backend mints a token scoped to one user and one Draft, TTL 1 h; the extension `fetch`es checkpoint and finalize directly. Relaying through the app tab was rejected: it would make a recording depend on that tab staying open and alive, which is exactly what the checkpoint design exists to survive.

### Stable ID and Chrome floor

The manifest pins a `key`, so the extension ID does not vary with install directory. Nothing in the connect flow addresses the extension by ID — the pin is for enterprise-policy installs and for later Web Store continuity. `minimum_chrome_version: "118"`: an attached `chrome.debugger` session resets the service-worker idle timer from 118, the one hard version dependency on record. Raise it if a slice needs a newer API. No ADR — the distribution choice is a reversible "for now".

### Version compatibility

Because the instance serves its own paired build, skew is an edge case rather than the normal path. The extension sends `X-Extension-Version` when it creates a recording session; the backend refuses below its declared minimum with a machine-readable code and a plain-language message linking the install page. `GET /api/extension/version` → `{ current, minimum_supported }` (unauthenticated) lets the app show an "update your extension" banner before the user tries to record. Warn-only was rejected: a recording that silently produces malformed Steps is worse than a refusal at the door.

## Sources

- [Host on Linux](https://developer.chrome.com/docs/extensions/how-to/distribute/host-on-linux) — off-store `.crx` installs are Linux-only; Windows and macOS require the Web Store.
- [externally_connectable](https://developer.chrome.com/docs/extensions/reference/manifest/externally-connectable), [Match patterns](https://developer.chrome.com/docs/extensions/develop/concepts/match-patterns) — no wildcard domains, no subdomains of effective TLDs.
- [Permissions list](https://developer.chrome.com/docs/extensions/reference/permissions-list) — `debugger` warns "Access the page debugger backend" plus "Read and change all your data on all websites"; no store policy bars it.
- Chrome disabling unpacked extensions across updates/profile reloads is forum-grade evidence, not first-party. It does not change the decision, but do not quote it as documented behavior.
