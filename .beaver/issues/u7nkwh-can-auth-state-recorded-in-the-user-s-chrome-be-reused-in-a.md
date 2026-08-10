---
id: u7nkwh
title: Can auth state recorded in the user's Chrome be reused in a Playwright worker, and what breaks it?
state: done
assignee: agent
priority: medium
labels:
    - roadmap:idnzwf
    - session:research
parent: idnzwf
created: 2026-08-08T07:07:40Z
updated: 2026-08-10T02:41:44Z
---

Research from primary sources. Users record while logged in; workers replay headlessly elsewhere. Answer:

- What auth state can an extension export (cookies incl. HttpOnly via chrome.cookies, localStorage, sessionStorage) and what can Playwright inject (storageState, CDP)?
- What invalidates transferred sessions: IP change, device fingerprinting, bot detection (Cloudflare, PerimeterX), token binding — and how commonly?
- What are the alternatives when transfer fails: credential-based login steps in the workflow, or interactive login via takeover then persisting the worker's own state?
- Security implications of storing session state server-side.

The answer gates the secrets/auth-state node and feeds the execution-architecture node.

## Notes

**agent** — 2026-08-10T02:41:44Z

## Question

Can authentication state recorded in a users Chrome be reused in a Playwright worker, and what breaks it?

## Answer

Yes, for ordinary cookie- and web-storage-based sessions: an extension can export permitted site cookies and page web storage, and a Playwright context can restore cookies and local storage through storage state. This is a best-effort bootstrap, not a portable-login guarantee. Some services bind sessions or clearance to client context, or require proof a copied token cannot provide. V1 therefore needs two supported recovery paths: credential-backed login steps, and interactive takeover in the worker browser followed by saving that workers own refreshed state. Treat every exported state blob as a bearer credential and keep it server-side only in a protected, revocable store.

## Findings

- Chrome extensions with the `cookies` permission and matching host permissions can read cookie objects, including their `value` and `httpOnly` fields; the API also exposes `secure`, `sameSite`, `storeId`, and partition-key data. Export must account for partitioned cookies and separate/incognito stores. [Chrome cookies API, updated 2025-08-11](https://developer.chrome.com/docs/extensions/reference/api/cookies)
- A content script executing on the target page can access that pages `localStorage` and `sessionStorage`; the extension service worker cannot access either directly. Host permission or a temporary `activeTab` grant is required for injection. Content scripts remain isolated from page JavaScript variables, and storage partitioning/iframes can make a simple origin-wide export incomplete. [Chrome storage and cookies](https://developer.chrome.com/docs/extensions/develop/concepts/storage-and-cookies) [Chrome content scripts](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts)
- Playwright `storageState`/`setStorageState` restores cookies and localStorage (and can include IndexedDB); `addCookies` accepts `httpOnly`, `secure`, `sameSite`, and partition-key attributes. Playwright does not persist sessionStorage automatically; capture it in-page and seed it with `addInitScript` before page scripts run. [Playwright authentication](https://playwright.dev/docs/auth) [Playwright BrowserContext API](https://playwright.dev/docs/api/class-browsercontext)
- Connecting Playwright to an existing Chromium browser over CDP is technically possible, but is Chromium-only and explicitly lower fidelity than the Playwright protocol. It is appropriate to control the live local browser, not a replacement for transferring it to a remote worker. [Playwright BrowserType API](https://playwright.dev/docs/api/class-browsertype)
- Cookies are not inherently IP- or device-bound: their standard defined attributes contain no IP/device field; a server assigns their semantics. Transfer fails only where the application or its WAF adds a contextual check. [RFC 6265](https://www.rfc-editor.org/rfc/rfc6265.html)
- Concrete failure cases exist: Microsoft Entra browser SSO binds a cookie to a TPM-protected device key; Token Binding allows a server to detect replay on another TLS connection; Cloudflare binds `cf_clearance` to a visitor/device and can re-challenge it; HUMAN Bot Defender performs per-request risk scoring using its own cookies and device-fingerprint storage. [Microsoft Entra PRT](https://learn.microsoft.com/en-us/entra/identity/devices/concept-primary-refresh-token?tabs=other-prt-issued%2Cwindows-prt-used%2Cwindows-prt-renewal%2Cwindows-prt-protection%2Cwindows-apptokens%2Cwindows-mfa) [RFC 8473](https://www.rfc-editor.org/rfc/rfc8473.html) [Cloudflare clearance](https://developers.cloudflare.com/cloudflare-challenges/concepts/clearance/) [HUMAN cookies/storage](https://docs.humansecurity.com/applications/use-of-cookies-web-storage)
- No examined primary source supports a universal IP-change rule or a population rate for IP binding, fingerprinting, Cloudflare, or HUMAN. Do not label these controls common or rare without product/run telemetry.
- A session identifier is a bearer credential equivalent to the strongest authentication method. OWASP recommends keeping its meaning server-side, protecting/encrypting sensitive session repositories, using HTTPS + Secure/HttpOnly/SameSite cookies, server-enforced idle and absolute expiry, rotation at authentication/privilege changes, active revocation, and no-store caching. HttpOnly does not prevent an XSS payload from making authenticated requests. [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)

## Unresolved

- Service-specific transfer success cannot be predicted before a real run; record it as a classified auth/challenge failure and route to login steps or takeover.
- Exact encryption/key-management, retention, backup, access-control, and revocation policy waits on the secrets/auth-state decision node.

## Sources

- Chrome extension documentation, current pages noted above.
- Playwright documentation, current pages noted above.
- RFC 6265 (2011) and RFC 8473 (2018).
- Microsoft Entra, Cloudflare, and HUMAN first-party documentation, accessed 2026-08-09.
- OWASP Session Management Cheat Sheet, accessed 2026-08-09.
