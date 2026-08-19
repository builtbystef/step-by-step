---
id: 94xanm
title: Extension distribution and the connect flow
state: in-progress
priority: medium
labels:
    - needs-review
depends_on:
    - lac27w
parent: d8ux2s
created: 2026-08-14T06:02:27Z
updated: 2026-08-19T02:47:53Z
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

**claude** — 2026-08-19T02:47:53Z

Built the package, the distribution channel, and both halves of the connect flow. Not closed: the permission dialog is the one step no automation can drive, and the attended pass is below.

**The package** — `apps/extension`, plain MV3 with no build step, so `src/` is both what Chrome loads and what the zip carries; the tests sit outside it. `manifest.json` pins a `key` (the id follows the package, not the install directory), declares `minimum_chrome_version: 118`, and holds `permissions: [storage, scripting]` with `optional_host_permissions: ["*://*/*"]` — a fresh install reaches no site until somebody names one. `service-worker.js` is a restartable coordinator: connection in `storage.local`, attempt in `storage.session`, listeners at the top level.

**Distribution** — `step_by_step_api.extension`. `GET /extension.zip` zips the directory with the manifest at the archive root; `GET /extension` is the install page beside it; `GET /api/extension/version` reports `{current, minimum_supported}`, current read from the served build's own manifest so an instance cannot claim a build it lacks. All three unauthenticated. `MINIMUM_SUPPORTED_VERSION` lives in `package.py` for bysmhd's session-create refusal to read.

**Connect** — the popup asks Chrome for the typed origin from the click itself (an `await` first would spend the gesture), the worker mints a 256-bit nonce, opens `<origin>/connect?nonce=…`, injects the bridge, and accepts the handshake only from this extension, in the top frame of the tab the attempt opened, at the attempt's origin, with the attempt's nonce. The fallback: `POST /api/extension/connect-codes` (authenticated, 201, single-use, 10 minutes) shown by the app's new `/connect` screen, spent at `POST /api/extension/connect` (unauthenticated, 401 `bad_code`).

Decisions a reviewer should know:

- **The code path asks for the same grant.** An extension's fetch to an origin Chrome has not granted is an ordinary cross-origin request, and this backend sends no CORS headers by design — so a connect code cannot be spent without the origin. The popup therefore re-requests it from the code button's own click, which is what the criterion's second clause says: one granted origin covers both the injection and the worker's fetch. A decline leaves the popup saying plainly that the permission is required.
- **The worker routes on the message's channel, not on whether the sender had a tab.** The rehearsal below caught the first version: an extension page opened in a tab — how anyone debugs the popup — was read as a content script and its commands refused. Commands are now gated on the sender being at this extension's own address, and the handshake's own judgement is what a page has to pass.
- **The content script is an injected function** (`lib/page-bridge.js`), not a file: a content script cannot import a module, and the protocol's names would otherwise be written twice with nothing keeping them equal. The worker passes them in as an argument.
- **The zip and the install page stay out of `/api` and out of the generated client** (`include_in_schema=False`): they are documents a browser is pointed at. `next.config.ts` proxies both in dev, or the links would work only inside the container.
- **A missing package is 503 `extension_unavailable` on those three routes, not a boot gate.** An instance without its extension still signs people in and runs Runs; what is unavailable is the download. The image carries the package and sets `EXTENSION_DIR`.
- **Connect codes**: twelve characters from an alphabet without I/L/O/0/1, stored as SHA-256 and never in the clear, single-use by row deletion, expired rows swept when one is issued. The route commits before it refuses, for the same reason the Sign-in Code's does.
- **The app's half of the protocol** is `apps/web/lib/extension-protocol.ts`; `extension-protocol.test.ts` reads `apps/extension/src/lib/handshake.js` and asserts the names match, because the extension has no build step and nothing importable from Next.

Tests. Fast tier: the handshake judgement, the instance-address reading, and the manifest's four promises (vitest); the version endpoint, the zip's contents, and the install page (pytest). Integration tier: connect codes over HTTP with a real Postgres — issue, spend, single-use, expiry under a controlled clock, paste-tolerant reading, 401 without a session, and the absence of any code in the clear. Browser tier, new at `apps/extension/tests/browser/` and wired into `pnpm test:browser` and the root `testpaths`: the package as it ships loads under the id its pinned key derives; a handshake from a cross-origin frame is never forwarded; the judgement refuses a wrong nonce, a wrong origin, and another tab. Two of the six load a **copy** whose manifest pre-grants the fixture origin — the state Chrome's dialog would leave behind — and drive the rest for real: popup click, opened tab, injected bridge, judged nonce, stored connection; and the code fallback against a fixture instance, wrong code then live one.

Verified by hand beyond the suite, against a real headless Chromium and the real dev stack (same pre-granted trick): the extension opened `localhost:3000/connect`, the Next screen handed the nonce over, the worker stored the origin, the app showed "Your extension is connected" and the popup showed the instance; and with a code minted through the real API, a wrong code was refused, the live one connected, and the same code a second time was refused as spent. That rehearsal is what found the routing bug above, a `disconnect` that threw when Chrome would not take a required permission back, and a race where a page on the same machine finishes loading before the attempt is written (the worker now asks the tab where it got to as well as waiting to be told).

**What is left for the user, and why this is not closed.** `chrome.permissions.request` raises a native Chrome dialog from a click in the popup, and no automation can click it. In a real Chrome, with the build from this instance loaded unpacked:

1. Popup → this instance's address → Connect → Chrome asks → **Allow**: the connect page opens and says the extension is connected, and the popup shows the instance.
2. Repeat and **Block**: the popup says the permission is required and opens the connect-code section.
3. With the grant declined, use the code: `/connect` → Show a connect code → paste into the popup → Connect with code → connected.
4. Disconnect in the popup: the instance is forgotten and Chrome's site access is handed back (chrome://extensions shows the site permission gone).

Close this issue to approve. If something in that pass is wrong, note the requested changes and remove `needs-review`.
