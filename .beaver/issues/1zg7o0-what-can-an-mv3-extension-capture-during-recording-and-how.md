---
id: 1zg7o0
title: What can an MV3 extension capture during recording, and how does it talk to the app?
state: done
assignee: agent
priority: medium
labels:
    - roadmap:idnzwf
    - session:research
parent: idnzwf
created: 2026-08-08T07:07:40Z
updated: 2026-08-10T02:26:53Z
---

Research from primary sources. Manifest V3 constrains what a recorder extension can do. Answer:

- Event capture: content scripts vs. chrome.debugger (CDP) — what each can observe (clicks, keystrokes, selects, downloads, navigations incl. cross-origin iframes and SPA route changes) and their UX costs (debugger banner).
- Capturing downloads and network responses at record time.
- Service-worker lifetime limits and their effect on a long recording session.
- Extension-to-backend communication and auth patterns (who owns the session: extension directly, or relayed through the web app?).

The answer gates the recording-extension prototype and feeds extension distribution (Frontier).

## Notes

**claude** — 2026-08-08T08:12:29Z

Pointer from the recorder research (f10wq3): the sharpest constraint this node must settle is the `debugger` permission. Computed ARIA role and accessible name are not reachable from a content script — no web-platform API exists (AOM Phase 4 shipped only as WebDriver endpoints), so they require `chrome.debugger` + CDP `Accessibility.*` from the service worker, which is the path DevTools Recorder itself takes. Accessible name derives from other elements (aria-labelledby, subtree text), so it must be computed at record time and cannot be reconstructed later. Since role+name sits at the top of the durable-selector ranking, this is a v1 decision, not a later optimization — deferring it means re-recording every workflow. Two open costs to weigh here: the persistent Chrome debugger infobar, and whether per-event `getPartialAXTree` is fast enough during live recording. See the full note on f10wq3.

**agent** — 2026-08-10T02:26:53Z

## Question

What can an MV3 extension capture while recording, and how should it communicate with the app?

## Answer

Use content scripts in every permitted frame for ordinary interaction capture, plus `chrome.webNavigation` for document and SPA navigation. For v1 durable selectors, computed accessibility role/name, and response bodies, attach `chrome.debugger` to the recording tab and use CDP; this makes the recorder visibly attached to the debugger. Observe downloads with `chrome.downloads`.

Do not run a long recording inside the MV3 service worker. Keep it as a restartable coordinator with persisted recording state. The extension should call the backend directly using a short-lived, scoped extension-session credential minted after an explicit connection from the authenticated web app. The web app bootstraps and observes the session; the extension owns active capture and the backend owns persisted data.

## Findings

### Event and navigation capture

- Content scripts share the page DOM from an isolated execution world, so listeners in every injected frame can record clicks, keyboard/input changes, and select changes. With `all_frames`, injection still requires matching/host access for each cross-origin frame; `about:blank` needs `match_about_blank`, while `data:`, `blob:`, and `filesystem:` can use `match_origin_as_fallback`. [Chrome content scripts](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts)
- Use `chrome.webNavigation` alongside DOM hooks: `onHistoryStateUpdated` reports History API changes and `onReferenceFragmentUpdated` reports hash changes, covering SPA navigation. [chrome.webNavigation](https://developer.chrome.com/docs/extensions/reference/api/webNavigation)
- `chrome.debugger` attaches CDP to a tab to instrument network interaction and inspect DOM/CSS; it requires the `debugger` permission. CDP’s Input domain is for dispatching input, not a general passive user-input stream, so content scripts remain the interaction-capture baseline. CDP is the needed route for the existing f10wq3 accessibility constraint: computed role/name must be captured at record time. [chrome.debugger](https://developer.chrome.com/docs/extensions/reference/api/debugger), [CDP Input](https://chromedevtools.github.io/devtools-protocol/tot/Input/)
- A debugger attachment has a visible Chrome warning bar; dismissing it ends the session, and opening DevTools detaches the extension. Make debugger attachment an explicit “recording active” action. [chrome.debugger](https://developer.chrome.com/docs/extensions/reference/api/debugger)

### Downloads and network responses

- `chrome.downloads` (the `downloads` permission) emits `onCreated` when a download begins and exposes URL/final URL, filename, MIME type, bytes, state, completion time, and interruption reason. It can create/correlate a download step, but is not a response-body API. [chrome.downloads](https://developer.chrome.com/docs/extensions/reference/api/downloads)
- `chrome.webRequest` observes URL, method, frame/tab IDs, lifecycle events and—with `requestBody`—request bodies, subject to `webRequest` plus host permissions. It exposes response headers/events but not response bodies; MV3 generally disallows `webRequestBlocking` except policy-installed extensions. [chrome.webRequest](https://developer.chrome.com/docs/extensions/reference/api/webRequest)
- CDP’s Network domain exposes request/response metadata and `Network.getResponseBody`, which returns request content. Therefore response-body extraction belongs on the debugger/CDP path, with filtering and size limits to avoid retaining unrelated sensitive traffic. [CDP Network 1.3](https://chromedevtools.github.io/devtools-protocol/1-3/Network/)

### Long recordings under MV3

- Chrome normally terminates an extension service worker after 30 seconds of inactivity; a single event/API request may not exceed five minutes and a `fetch()` response may not take more than 30 seconds. A worker can restart on an event; Chrome advises persisted state rather than globals. [Extension service-worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle)
- An active `chrome.debugger` session (Chrome 118+) resets the worker idle timer, but this is not a durable-recording guarantee. Persist recording ID, tab ID, attachment state, and buffered-step checkpoints after each event. [Extension service-worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle)
- If later requirements include media/screen recording, Chrome documents worker-to-offscreen-document handoff (Chrome 116+). An offscreen document with a non-`AUDIO_PLAYBACK` reason has no lifetime limit, but it is unnecessary for DOM-step capture. [Audio recording and screen capture](https://developer.chrome.com/docs/extensions/how-to/web-platform/screen-capture), [chrome.offscreen](https://developer.chrome.com/docs/extensions/reference/api/offscreen)

### App communication and authentication

- Extension contexts communicate through `runtime.sendMessage`/ports. A web app may initiate a message to an extension only through a narrow `externally_connectable.matches` allowlist; extensions cannot message arbitrary web pages directly. Treat content-script messages as untrusted. [Chrome message passing](https://developer.chrome.com/docs/extensions/develop/concepts/messaging)
- Extension service workers/pages can use `fetch()` to permitted backend hosts, whereas content scripts stay subject to the page origin. Put host permission on the backend API origin. [Cross-origin network requests](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests)
- Recommended ownership boundary (an inference from those APIs): the authenticated app conducts a user-initiated connection handshake; the backend mints a short-lived, recording-scoped credential bound to the extension installation/session; the extension calls the backend directly to create, checkpoint, and finalize recordings. Validate source origin, sender, tab context, and every content-script payload.
- `chrome.identity` is suitable only when the extension itself is an OAuth client (notably Google OAuth); it is not required for the first-party app-token handshake. [chrome.identity](https://developer.chrome.com/docs/extensions/reference/api/identity)

## Unresolved

- Measure per-event CDP accessibility query cost in the recording-extension prototype.
- Chrome Web Store versus unpacked distribution and update policy remains a product decision; it is now sharp enough for a separate session.

## Sources

- [Chrome content scripts](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts)
- [chrome.webNavigation](https://developer.chrome.com/docs/extensions/reference/api/webNavigation)
- [chrome.debugger](https://developer.chrome.com/docs/extensions/reference/api/debugger)
- [chrome.downloads](https://developer.chrome.com/docs/extensions/reference/api/downloads)
- [chrome.webRequest](https://developer.chrome.com/docs/extensions/reference/api/webRequest)
- [CDP Network 1.3](https://chromedevtools.github.io/devtools-protocol/1-3/Network/)
- [Extension service-worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle)
- [Chrome message passing](https://developer.chrome.com/docs/extensions/develop/concepts/messaging)
- [Cross-origin network requests](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests)
- [chrome.identity](https://developer.chrome.com/docs/extensions/reference/api/identity)
