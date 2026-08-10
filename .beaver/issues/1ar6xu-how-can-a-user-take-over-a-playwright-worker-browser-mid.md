---
id: 1ar6xu
title: How can a user take over a Playwright worker browser mid-run, and hand it back?
state: done
assignee: agent
priority: high
labels:
    - roadmap:idnzwf
    - session:research
parent: idnzwf
created: 2026-08-08T07:07:40Z
updated: 2026-08-10T02:28:17Z
---

Research from primary sources. The run pauses on CAPTCHA/MFA; the user must see the worker's browser, act in it, and resume automation. Answer:

- What are the viable mechanisms: CDP screencast + input injection, noVNC/x11 over the worker, browser-streaming providers (Browserbase, Anchor, Steel, etc.), Playwright-specific options?
- How do existing tools (Skyvern, Browserbase session takeover, Airtop, etc.) implement human-in-the-loop takeover?
- Latency/quality/security trade-offs of each; what each implies for worker isolation (container per run? persistent browser?).
- How is the pause detected or declared (explicit step type vs. heuristic detection)?

The answer gates the execution-architecture node and the takeover UX (Frontier).

## Notes

**agent** — 2026-08-10T02:27:52Z

## Question

Research how a user can take over a Playwright worker browser mid-run for CAPTCHA/MFA, then hand it back.

## Answer

Use one isolated, headed Chromium instance per run and make human intervention an explicit `humanAuth` / `humanChallenge` workflow step. Pause at a known boundary, offer authenticated remote access to that same browser session, and resume only after a workflow-defined success predicate.

For self-hosted v1, implement remote viewing and input through a full browser desktop stream (headed Chromium in the run container with X11 + an authenticated web VNC gateway). It carries the real browser UI and needs substantially less bespoke input/rendering work than CDP screencast. Keep CDP screencast plus input injection as a later, page-only optimization: it is experimental, not a full browser/OS view, and requires the product to own frame transport, coordinate mapping, focus, and input arbitration. A hosted browser provider is an optional deployment alternative, not the core execution architecture.

Do not attempt universal CAPTCHA/MFA detection. Known DOM/URL/network patterns may raise a diagnostic review request, but an explicit step with an exact success predicate is the reliable automation contract.

## Findings

### 1. Browser-control mechanisms

- CDP `Page.startScreencast` emits base64 JPEG/PNG frames with quality, dimensions, and every-Nth-frame controls; frame metadata includes scroll offsets and viewport information. CDP `Input` can inject mouse, keyboard, touch, drag, text/IME, and gestures. This is viable for page-only remote control, but requires image transport/decoding, coordinate translation, and input sequencing. The screencast API is Experimental. Source: [CDP Page](https://chromedevtools.github.io/devtools-protocol/tot/Page/) and [CDP Input](https://chromedevtools.github.io/devtools-protocol/tot/Input/) (tip-of-tree, accessed 2026-08-09).
- Chrome documents that a CDP screencast contains page content, not browser chrome, OS UI, or virtual keyboard, and warns that screencasting lowers frame rates. Source: [Chrome remote debugging](https://developer.chrome.com/docs/devtools/remote-debugging) (accessed 2026-08-09).
- Playwright can attach to Chromium over CDP and send raw CDP commands using `CDPSession`, but `connectOverCDP` is Chromium-only and Playwright calls it lower fidelity than its native protocol. Source: [BrowserType.connectOverCDP](https://playwright.dev/docs/api/class-browsertype#browser-type-connect-over-cdp) and [CDPSession](https://playwright.dev/docs/api/class-cdpsession) (current docs, accessed 2026-08-09).
- A remote-debugging endpoint is privileged browser control. Chrome requires a non-default user-data directory for remote debugging as of Chrome 136; Playwright warns against exposing its browser-server socket on a network. Bind control endpoints to the container/loopback and put authenticated encrypted user access behind an application gateway. Source: [Chrome remote-debugging security change](https://developer.chrome.com/blog/remote-debugging-port) and [Playwright launchServer security note](https://playwright.dev/docs/api/class-browsertype#browser-type-launch-server) (accessed 2026-08-09).

### 2. Existing HITL implementations

- Browserbase Live View provides interactive watch/click/type/scroll access to a running session, including read-write or read-only embeds; its 2FA guidance hands the Live View URL to the end user. A saved Context can preserve cookies, tokens, and local storage for later sessions. The documentation does not establish exclusive control locking. Source: [Session Live View](https://docs.browserbase.com/platform/browser/observability/session-live-view) and [Website authentication](https://docs.browserbase.com/platform/identity/authentication) (accessed 2026-08-09).
- Airtop and Steel likewise document embedded interactive live views that act on the same session as automation. Steel explicitly says user actions affect the actual browser session; both document opt-in cross-run profile persistence. Neither source documents exclusive handoff arbitration. Source: [Airtop Live View](https://docs.airtop.ai/guides/how-to/creating-a-live-view), [Airtop Profiles](https://docs.airtop.ai/guides/how-to/saving-a-profile), [Steel HITL](https://docs.steel.dev/overview/sessions-api/human-in-the-loop), and [Steel Profiles](https://docs.steel.dev/overview/profiles-api/overview) (accessed 2026-08-09).
- Skyvern documents a Human Interaction block that pauses for a reviewer input/approval and resumes after a configurable timeout; reviewed first-party documentation does not establish an interactive browser-takeover API. Source: [Skyvern blocks](https://www.skyvern.com/docs/cloud/building-agents/configure-blocks#human-interaction) (accessed 2026-08-09).

### 3. Pause detection and resumption

- Playwright supports known alternative UI outcomes with `locator.or()` and recommends waiting for the final URL or authenticated UI before saving authenticated state. Define the post-human success predicate using these application-specific signals. Source: [Locator alternatives](https://playwright.dev/docs/locators#matching-one-of-the-two-alternative-locators) and [Authentication](https://playwright.dev/docs/auth#basic-shared-account-in-all-tests) (current docs, accessed 2026-08-09).
- Frame navigation, new-page, and request events can observe known provider patterns but provide no semantic CAPTCHA/MFA classification; timeouts, DOM text, origins, and status codes are heuristics with false positives/negatives. Source: [BrowserContext events](https://playwright.dev/docs/api/class-browsercontext#browser-context-on-framenavigated), [request event](https://playwright.dev/docs/api/class-browsercontext#browser-context-on-request), and [Request](https://playwright.dev/docs/api/class-request) (current docs, accessed 2026-08-09).
- Playwright has deliberate pause/resume APIs, but native JavaScript dialogs are not an auth signal: an unhandled listener freezes page execution and a page with no listener auto-dismisses dialogs. Source: [Debugger](https://playwright.dev/docs/api/class-debugger), [Page.pause](https://playwright.dev/docs/api/class-page#page-pause), and [Dialogs](https://playwright.dev/docs/dialogs) (current docs, accessed 2026-08-09).

### 4. Isolation, quality, and security

- Make the browser container and profile exclusive to one run. Automation and the user necessarily share that single stateful session during takeover; suspend automation actions while human control is active to avoid races. This arbitration policy is a product inference: the reviewed provider and protocol docs expose shared access but no exclusive-lock primitive.
- Do not persist a browser profile by default. Save worker-side authentication state only as an explicit, encrypted, per-user choice after a successful human login; providers similarly make context/profile persistence explicit. Session cookies and state are bearer credentials and must never appear in source control or ordinary logs. Playwright warns its storage state may contain impersonation-capable cookies and headers. Source: [Playwright Authentication](https://playwright.dev/docs/auth) (current docs, accessed 2026-08-09).
- Full desktop streaming should offer the most faithful UI (browser chrome, native MFA helpers where present) but consumes a headed display server and must be safely gatewayed. CDP relay reduces stack components but is page-only and trades quality/latency against image size, quality, and sampling. Hosted providers reduce operations work while adding external credential/session custody and vendor dependence.

## Unresolved

- The exact streaming stack, viewer authentication/authorization, timeout behavior, and user-facing takeover controls are product/UX decisions; resolve them in a dedicated prototype.
- First-party sources reviewed do not document a universal CAPTCHA/MFA detector or a formal exclusive-control handoff for the hosted live-view products.

## Sources

The primary-source URLs cited adjacent to each finding, accessed 2026-08-09.

**agent** — 2026-08-10T02:28:17Z

Supplement to Findings 1: noVNC is a browser-based VNC client application/library, supports desktop scaling and mouse/clipboard/touch interactions, and requires a WebSocket-capable VNC server or proxy. Its documented `novnc_proxy` can bind on localhost. This establishes that an X11/VNC server plus a web VNC gateway is a viable full-desktop streaming mechanism; application authentication and authorization remain our responsibility. Source: [noVNC README](https://github.com/novnc/noVNC) (project source, accessed 2026-08-09).
