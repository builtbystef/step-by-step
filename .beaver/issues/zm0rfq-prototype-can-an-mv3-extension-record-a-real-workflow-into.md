---
id: zm0rfq
title: 'Prototype: can an MV3 extension record a real workflow into semantic steps?'
state: done
assignee: claude
priority: medium
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - f10wq3
    - 1zg7o0
parent: idnzwf
created: 2026-08-08T07:08:04Z
updated: 2026-08-10T22:43:55Z
---

Disposable prototype (prototype skill), live with the user. With selector strategy (f10wq3) and MV3 capabilities (1zg7o0) researched, answer by building:

- Record a small real flow (e.g. log in to a demo site, search, extract a value, download a file) with a throwaway extension using the chosen capture approach.
- Do the captured events map cleanly to the intended semantic steps with durable selectors?
- Replay the captured steps once in Playwright to expose the record→replay gap early.

Feasibility verdict + findings gate the data-model decisions hardening into a spec; the code is disposable.

## Notes

**claude** — 2026-08-10T22:43:55Z

## Question

Can an MV3 extension record a real workflow into semantic steps with durable selectors, and do those steps replay in Playwright?

## Verdict

Yes — user-confirmed feasible. A live-recorded flow on the-internet.herokuapp.com (login, extract, dropdown select, file download) produced 11 semantic steps that replayed 11/11 in Playwright, every step resolving on its rank-0 selector candidate. Code: branch `prototype/mv3-recorder` (disposable; `README.md` there has run instructions).

## Findings a spec must honor

- **Capture split works as researched (f10wq3, 1zg7o0):** content script computes ranked selector candidates (testid → role+name → placeholder/label/alt/text/title → css) and verifies each unique against the live DOM at record time; the service worker owns `chrome.debugger`/CDP for computed role+name; `chrome.webNavigation.onCommitted` transition types separate click-caused navigations (attach to the click as `assertedNavigation`) from typed ones (standalone navigate step); `chrome.downloads.onCreated` correlates a download to the causing click within a time window.
- **CDP role/name cost is a non-issue:** 11–35ms avg per event (max 64ms live); the user perceived no sluggishness. The f10wq3 open question is answered.
- **But the CDP path has sharp edges the spec must encode:** (1) query at pointerdown/focusin, not at the action — a navigating click destroys the element before a click-time query lands (the Login button's uniqueness check lost exactly this race); (2) use `Runtime.evaluate` → objectId → `Accessibility.getPartialAXTree`, never `DOM.getDocument` nodeIds, which go stale across navigations and concurrent queries; (3) recIds must be scoped per page load or caches collide across navigations; (4) step assembly must await the in-flight ax query (bounded) or a fast click loses its best candidate; (5) all step-producing events (interactions, navigations, downloads) must flow through one serialized queue or steps land out of interaction order.
- **Role+name transfers exactly:** CDP's computed accessible name for the Login button included the icon-font glyph (` Login`) and Playwright's `get_by_role(..., exact=True)` computed the identical name at replay. `Accessibility.queryAXTree` verifies record-time uniqueness of role+name (ignore `ignored` nodes).
- **Replay policy validated:** ordered first-match-wins fallback (resolve candidates by rank, first with count==1 acts) worked; `expect_download` wraps a click carrying a download; extract replays as text_content comparison (matched byte-for-byte). Feeds wljln8.
- **Debugger infobar:** persists for the whole recording; dismissing it detaches the debugger and ends role/name capture — Chrome offers no close-and-reopen (user asked; impossible). Recording UX must present the bar as the fixed, visible cost of an active recording.
- **Fill capture on `change` yields clean semantic fills** with an isPassword flag (hook for 7o0nmx secret handling). Password value was captured in clear in the prototype; the real recorder must not persist it.
- **Extract-mode affordance:** a page-injected toggle (next click = extract) worked and recorded `capturedText` + selectors; preventDefault keeps the extract click side-effect-free.
- **Automated record-loop testing is possible:** Playwright can drive the extension headless via `--load-extension` (harness `debug_record.py` on the branch). Environment quirks, not extension bugs: clicking a native `<select>` opens a browser-level popup CDP input cannot close, swallowing all later clicks; Playwright never observes downloads while the extension's debugger is attached.

## Not exercised

iframes, shadow DOM, SPA route changes, selector drift on a changed page — flow ran on a stable MPA demo site. Drift behavior is wljln8's ground.
