---
id: d8ux2s
title: Recording, editing, and storage of Workflows
state: todo
labels:
    - spec
depends_on:
    - 8iuuh8
    - f10wq3
    - ds8zyn
    - 1zg7o0
    - zm0rfq
    - wljln8
    - 3iwv5i
created: 2026-08-11T18:47:59Z
updated: 2026-08-15T04:14:42Z
---

## Problem Statement

A user who wants to automate a browser task should not have to write code or CSS selectors. They perform the task once in their own Chrome, and the tool must turn those clicks, keystrokes, and navigations into a named, editable Workflow of semantic Steps — durable enough to replay weeks later on a page that has shifted, safe enough that a recorded password never lands in storage, and honest enough to warn immediately when it captures something it will not be able to replay. Afterward they need to refine that Workflow — rename steps, bind values to Variables, repair a target the site changed — without re-recording everything, and publish it in a form that Schedules and Batches can execute while editing continues.

## Solution

A Chrome extension records interactions in the user's real browser session and turns each one into a semantic Step with a ranked, record-time-verified list of selector candidates. The extension talks directly to the backend through a short-lived recording-scoped credential minted by the web app. Recorded Steps land in the Workflow's single mutable Draft. The web app's editor shows the Draft as a card list that reads as sentences ("Type {{password}} into Password field"), with selector health, Variables, and envelope controls on each card. Publishing snapshots the Draft as an immutable numbered Version — the thing Runs, Schedules, and Batches execute. When a site changes, the editor shows Selector Drift where it happened, and a Re-pick through the extension replaces one Step's candidate list without touching anything else.

## User Stories

1. As a user, I want to record actions I perform on a website as a named Workflow of semantic Steps, so that I can automate a task without writing code.
2. As a user, I want each recorded Step to store several verified ways of finding its element, ranked best-first, so that my Workflow survives page changes that would break a single selector.
3. As a user, I want a recorded password to be bound to a secret Variable instead of being stored, so that my credentials never sit in a Workflow.
4. As a user, I want an immediate plain-language warning when I record something the tool cannot reliably replay, so that I am not surprised by a failure weeks later.
5. As a user, I want to edit my Workflow — labels, order, values, Variables, timeouts, optional/disabled flags — in a visual editor, so that refining does not mean re-recording.
6. As a user, I want to declare Variables and reference them inside step values, so that one Workflow runs with different inputs.
7. As a user, I want to test-run my Draft without publishing, so that I can verify edits safely.
8. As a user, I want to publish a Version and see a step-level diff of what changed, so that I control what Schedules and Batches execute.
9. As a user, I want the editor to flag Steps whose selectors have been drifting in recent Runs, so that I repair targets before they break.
10. As a user, I want to repair one Step by re-picking its element on the live page, so that one changed button does not force a full re-record.
11. As a user, I want a crashed or restarted recording session to keep the Steps captured so far, so that a long recording is never lost.

## Implementation Decisions

### Storage

- A Workflow row carries: the owning Organization (per ADR 0005, exactly one), name, workflow-level default step timeout (default 30 s, set explicitly — never inherited from a Playwright binding default), and per-workflow takeover timeout (default 30 min).
- The Draft and each Version store their Steps as **one JSONB array on their own row** — not per-step rows. Publish copies the Draft's array verbatim into a new immutable Version N in a single insert. Per-type payload changes need no migrations.
- **Variable declarations live in the same versioned document as the Steps**: the Draft document holds `steps` and `variables`; publish snapshots both. A Version is therefore self-contained and executable forever.
- Step `id` is an app-minted UUID assigned when the Step is created (at capture or editor add) and **never rewritten by edits or publish** — stable ids across Versions are what make cross-version Step history and Selector Drift aggregation possible.
- **Save-time validation rejects any step array containing duplicate step ids.** Duplicating a Workflow mints fresh ids for every Step. (Integrity is app-enforced; the database cannot see inside the JSONB.)
- A Run pins a Version; a test run of the Draft instead embeds its own frozen snapshot of the Draft document and is flagged a test run. No Version is minted by testing. Schedules and Batches always execute the latest published Version.

### Step document

The Step envelope and per-type payloads (the contract at the API and recorder seams):

```
Step = {
  id: uuid,
  type: "navigate" | "click" | "type" | "select" | "download"
      | "extract" | "wait" | "pause-for-takeover",
  label: string,          // auto-generated at capture, user-editable
  optional: boolean,      // target never appears -> skip, don't fail
  disabled: boolean,      // stays in the Workflow, does not execute
  timeoutMs?: number,     // falls back to the workflow default
  payload: <per type, below>
}

Target = {
  candidates: SelectorCandidate[],   // ranked best-first, all verified unique at capture
  frame?: FramePath,                 // positional index path + name + url per hop
  unsupported?: { reason: "closed-shadow-root" | "cross-origin-frame",
                  warning: string }  // plain-language, written at capture
}

SelectorCandidate = {
  kind: "testid" | "role" | "placeholder" | "label" | "alt"
      | "text" | "title" | "css",
  value: string,
  shadowPath?: string[]   // one selector per open shadow-root hop, outermost first
}

payload by type:
  navigate:  { url: string }                      // {{name}} interpolation allowed
  click:     { target: Target, assertedNavigation?: boolean }
  type:      { target: Target, value: string }    // {{name}} interpolation allowed
  select:    { target: Target, value: string }
  download:  { target: Target }                   // a click expected to produce a file
  extract:   { target: Target, outputName: string,
               mode: "scalar" | "list",
               attribute?: string,                // absent = text content
               fields?: { name: string, subSelector: string,
                          attribute?: string }[] }   // list mode only, flat records
  wait:      { mode: "duration", durationMs: number }
           | { mode: "element", target: Target }
  pause-for-takeover: { message?: string, timeoutMs?: number }
```

- Candidate ranking follows Playwright's codegen score order: test-id → role+name → placeholder → label → alt-text → text → title → CSS. Every persisted candidate was verified at capture to resolve **uniquely** to the recorded element on the live page.
- Variable references are `{{name}}` template interpolation inside string values (`type` value, `navigate` URL); literal text and Variables mix freely. Secret masking keys off the Variable's secret flag, not the syntax.
- Extraction: scalar mode yields one named value (text or an attribute); list mode yields a flat list of records, each field bound to a sub-selector within the repeating element. No nesting.

### Recorder (extension)

- Capture split: content scripts in every permitted frame capture interactions and compute the ranked candidate list against the live DOM; the service worker owns `chrome.debugger`/CDP for computed ARIA role and accessible name (not reachable from a content script); `chrome.webNavigation` classifies navigations (click-caused → `assertedNavigation` on the click; typed → standalone `navigate` Step); `chrome.downloads.onCreated` correlates a download to its causing click within a time window, producing a `download` Step.
- Five normative capture-ordering rules (each one prevents a race the prototype hit):
  1. Query the accessibility tree at `pointerdown`/`focusin`, never at the action — a navigating click destroys the element before an action-time query lands.
  2. Address elements via `Runtime.evaluate` → objectId → `Accessibility.getPartialAXTree`; never `DOM.getDocument` nodeIds (stale across navigations and concurrent queries).
  3. Element correlation ids are scoped per page load, or caches collide across navigations.
  4. Step assembly awaits the in-flight accessibility query, bounded, or a fast click loses its best candidate.
  5. All step-producing events — interactions, navigations, downloads — flow through one serialized queue, or Steps land out of interaction order.
- Role+name uniqueness is verified via `Accessibility.queryAXTree`, ignoring `ignored` nodes. Implicit roles are captured, not just explicit `role=` attributes.
- The service worker is a **restartable coordinator**, never a long-running holder of state: recording id, tab id, attachment state, and buffered-step checkpoints persist after each event, surviving the 30 s idle kill.
- The debugger infobar is presented as the fixed, visible cost of an active recording. If the user dismisses it (or opens DevTools), role/name capture is irrecoverable — **the recording ends**, keeping every Step captured so far; the user may save or discard.
- **Secrets:** a password-field value never leaves the content script — not even to the service-worker buffer. The Step is emitted as a `type` Step with an empty value and a *needs-secret* marker. The recording save screen refuses to finalize until every needs-secret Step is bound to a secret Variable (new or existing), landing as `{{name}}`; the backend rejects a finalize containing an unresolved marker. Non-password literals convert to Variables later in the editor.
- **Unsupported structures:** at capture, a target inside a closed shadow root, or in a frame the extension cannot inject into, triggers an immediate inline warning in plain, non-technical language (e.g. "This part of the page is sealed off in a way that automation can't reach later — this step will likely fail when the workflow runs"). Recording never blocks: the Step is recorded as well as possible and permanently carries the `unsupported` flag, which the editor renders as a red badge, distinct from the amber fragile badge.
- Extract mode is an explicit toggle ("next click = extract"); the extract click is side-effect-free (`preventDefault`), recording captured text plus selectors.
- No response-body capture. The extension never uses `Network.getResponseBody`; nothing network-level is retained.

### Distribution, updates, and connection (n52g83)

- **Unpacked distribution.** v1 ships no Chrome Web Store listing and no self-hosted `.crx`/`update_url` (off-store `.crx` installs are Linux-only). The backend serves the extension build paired with it at `GET /extension.zip`, alongside an install page (unzip → `chrome://extensions` → Developer mode → Load unpacked) that the app UI links. Accepted costs: Developer mode, no auto-update, and Chrome may disable an unpacked extension across updates or profile reloads. The install docs note in one sentence that Windows/macOS fleets can force-install through enterprise policy; nothing is built for it.
- **Stable ID.** The manifest pins a `key`, so the extension ID does not vary with install directory. Nothing in the connect flow addresses the extension by ID; the pin exists for enterprise-policy installs and for later Web Store continuity.
- **`minimum_chrome_version: "118"`** — an attached `chrome.debugger` session resets the service-worker idle timer from 118. Raise it if a slice needs a newer API.
- **Version compatibility.** Because the instance serves its own build, skew is an edge case, not the normal path. The extension sends `X-Extension-Version` on session creation; the backend refuses below its declared minimum with a plain-language message linking the install page. `GET /api/extension/version` → `{ current, minimum_supported }` (unauthenticated) lets the app show an "update your extension" banner before a recording is attempted.

### Recording session protocol

App-first: the Workflow is created and named in the web app; recording targets its Draft. Re-recording a Draft that already has Steps **replaces** them, behind a confirm in the app before the session starts. Starting is deliberately two gestures: **Start recording** in the editor creates a pending session in the extension, then the user opens the intended target tab and confirms in the extension popup. That popup click requests the target origin through `chrome.permissions.request` when needed and starts recording after the grant. A remembered per-origin grant skips Chrome's permission dialog but not the popup confirmation. Declining leaves the pending session idle and injects nothing. The extension never asks for all-sites access at install time.

**The extension opens the channel, not the app.** `externally_connectable.matches` cannot express an arbitrary self-hosted origin — wildcard domains and subdomains of effective TLDs are rejected, so `<all_urls>`, `*://*/*`, and `*://*.com/*` are all invalid — and a self-hoster's origin is unknown at build time. One shared build therefore cannot be messaged by the app. Instead:

```
Connect (once per instance, in the extension popup):
  user enters the instance URL
  -> chrome.permissions.request for that origin   // from a user gesture;
                                                  // optional_host_permissions: ["*://*/*"]
  -> extension opens the app's connect page there, injects its content script
  -> page hands the handshake over window.postMessage
  Fallback when the grant is declined: the app displays a one-time connect
  code, the user pastes it into the popup, the extension exchanges it at the
  backend. The one granted origin covers both content-script injection and
  the service worker's fetch.

Web app -> backend:
  POST /api/workflows/{workflowId}/recording-sessions   // X-Extension-Version
    -> { sessionId, token }        // token scoped to one user + one Draft, TTL 1 h

Web app -> extension (content script on the connected origin, postMessage):
  { sessionId, token, backendOrigin, workflowName, mode: "record" | "repick",
    stepId? }                      // stepId only for repick; stored as pending

Target tab -> extension popup (one user confirmation per recording):
  click Start recording
  -> chrome.permissions.request for the target origin when not already granted
  -> attach debugger and inject recorder-content.js only after the grant

Extension -> backend (direct fetch, Authorization: token):
  POST /api/recording-sessions/{sessionId}/checkpoint
    { seq, steps: Step[] }         // idempotent by seq; full buffer each time
  POST /api/recording-sessions/{sessionId}/finalize
    { steps: Step[], variables: VariableBinding[] }
    -> writes the Draft (replace); rejects unresolved needs-secret markers
```

- The extension calls the backend directly; checkpoints are never relayed through the app tab, so a closed or dead tab cannot cost a recording.
- Checkpoints exist so a killed service worker or expired token loses nothing: on token expiry mid-recording the app re-mints against the same session and the extension resumes; buffered Steps survive locally and on the server.
- Every extension message is treated as untrusted: origin, sender, tab context, and payload are validated; content-script messages doubly so. A `window.postMessage` handshake is accepted only from the connected origin and only when it matches a nonce the extension generated for that connect attempt.
- A **Re-pick session** is the same handshake scoped to one Step (`mode: "repick"`). The user navigates to the page themselves — the Workflow is not replayed to get there — and clicks the intended element; the extension computes a fresh verified candidate list and finalizes it to the session. The editor then shows old vs. new candidate lists and the user confirms, which patches that one Step in the Draft. Escape hatch: candidates are plain stored data and can be hand-edited in the editor.

### Editor (web app)

- Layout: a vertical inline card list whose card summary is a narrative sentence with Variable pills and target tokens; bold editable label on top; click expands the full form in place; hover tools for reorder/disable/delete; right-hand badge column: optional / off / timeout override / fragile target / unsupported target.
- Selector panel per targeting Step: collapsed shows "How this step finds '<element>'" with a health badge — green "N ways to find it — verified when recorded", amber "fragile — only position-based selectors", red for unsupported targets. Expanded shows ranked candidate rows (kind chip, value, uniqueness check), move-to-top / remove, "Pick element again…" (Re-pick) and "Add selector by hand".
- Variables drawer: name, secret flag, delete; each row shows "used by N steps" with highlight-and-scroll to usages. **Deleting a used Variable is refused**; unused Variables are flagged amber. `{{name}}` pills insert via dropdown; secret pills are styled distinctly and masked in the test-run form.
- Header: workflow name; Draft chip ("unpublished changes" amber / "in sync with vN" green); version dropdown listing Draft + all Versions; past Versions open read-only with restore-to-Draft.
- Test run: a modal prompts for per-run Variable values with secrets masked; the Run is flagged a test run; no Version is minted.
- Publish: a modal shows a step-level diff against the last Version, then mints Version N+1 and flips the chip to in-sync.
- Selector Drift surfaces in the editor as an aggregate warning badge on the Step, computed over recent Runs from Step Results' matched-candidate rank — the editor is where repair happens, so the warning lives there.

### Replay selector resolution (module contract)

The other half of the selector contract, consumed by the Workers (their execution spec references this):

```
resolve(page, target: Target, deadline) -> Element | SelectorFailure

Walk candidates in rank order; the first that resolves to exactly one
element wins. A candidate matching zero or several elements is skipped —
ambiguity is always rejected; .first()/.nth() and locator.or() are never
used. If the full list fails, re-walk it in a loop until the step
timeout expires: the timeout IS the retry budget; no separate retry
counter. On success, record the matched candidate's rank in the Step
Result (the Selector Drift signal). On expiry -> SelectorFailure.
```

Playwright actionability checks (visible, stable, enabled, receives events) apply within each attempted action as usual. Timeouts are always set explicitly.

## Dependencies

None beyond the stack already settled for the project (Next.js/TypeScript frontend, FastAPI/Python backend, PostgreSQL storage, Playwright in the Workers). The extension is plain MV3 JavaScript — the prototype needed no framework and v1 does not add one. The extension test harness drives headless Chromium with the unpacked extension through Playwright, which the project already carries.

## Testing Decisions

Three seams:

1. **Backend HTTP API** — the primary seam; tests speak HTTP to the app with a real Postgres. Good tests here assert external behavior: a Draft save with duplicate step ids → rejected (validation error naming the duplicate); duplicate-a-Workflow → every Step id differs from the source while order and payloads match; publish → a new immutable Version whose steps byte-match the Draft, and a step-level diff listing added/removed/changed Steps; finalize with an unresolved needs-secret marker → rejected; checkpoint after simulated session death → finalize still yields the full Step list; expired token → 401, re-mint against the same session resumes; re-pick finalize → exactly one Step's candidate list changes and its step id is preserved; deleting a Variable used by a Step → refused; a session create carrying an `X-Extension-Version` below the declared minimum → refused with a machine-readable code, and `GET /api/extension/version` reports the same minimum.
2. **Recorder capture pipeline at the extension boundary** — Playwright drives headless Chromium with the unpacked extension over local fixture pages; tests assert on the emitted Step JSON. Worked examples: a click on `<button data-testid="save">Save</button>` → a `click` Step whose candidate list starts with the testid candidate, role+name candidate present and verified; typing into a password field → a `type` Step with empty value and needs-secret marker, and the literal value appears nowhere in any emitted message; a click that navigates → one `click` Step with `assertedNavigation`, no separate `navigate` Step; a typed URL change → a standalone `navigate` Step; interactions inside a closed shadow root → the Step carries `unsupported` with the plain-language warning; a rapid click sequence → Steps in interaction order (the serialized-queue rule observable from outside). Known harness quirks from the prototype: native `<select>` popups and download events behave differently under an attached debugger — select is tested via `select_option`, and download-step capture is exercised in a real Chrome session, not the headless harness.
3. **Selector resolution module** — pure-module tests against fixture pages. Worked examples: candidates [testid, role+name, css] where testid is gone and role+name matches one element → resolves via rank 1 and the result records rank 1; a candidate matching two elements → skipped, resolution continues down the list; all candidates ambiguous or missing → SelectorFailure at timeout, not before the deadline; an element that appears 2 s after navigation with a 30 s timeout → resolved (the re-walk loop observable from outside).

Prior art: none — this spec creates the first code and the first tests in the repository.

## Out of Scope

- Loop, conditional, and assertion step types; step-output-as-input; computed Variables (8iuuh8).
- Nested extraction records (ds8zyn).
- Self-healing selectors, automatic selector regeneration, weighted multi-locator voting (f10wq3, wljln8).
- Version pinning for Schedules and Batches (ds8zyn).
- Response-body capture of any kind (this spec).
- Chrome Web Store publication (n52g83) — deferred, not rejected; it carries its own prerequisites (developer account, review, permission justification for `debugger` and broad optional host access) and sits on the roadmap's Frontier.
- Self-hosted `.crx` with an `update_url`, and any extension auto-update mechanism (n52g83) — off-store `.crx` installs work on Linux only.
- Enterprise-policy deployment of the extension (n52g83) — documented in one sentence, not built.
- `externally_connectable`-based app-to-extension messaging (n52g83) — its match patterns cannot express an arbitrary self-hosted origin.
- Execution architecture: Workers, queues, Run lifecycle, artifacts, live run view, takeover UX — the backend + workers + live-run area's spec. This spec defines only the selector-resolution contract that area consumes.
- Secret and Auth State storage, encryption, and vault UX — the secrets area (7o0nmx and its spec). This spec only binds `type` Steps to secret Variables by name.
- Editor UI automation — editor behavior is tested at the API seam; the layout was validated by prototype 3iwv5i.

## Further Notes

- Reference implementations: branch `prototype/mv3-recorder` (capture split, CDP timing, replay validation — 11/11 Steps on rank-0 candidates) and branch `prototype/workflow-editor` (the chosen hybrid layout is variant A). Both are disposable prototypes: steal patterns, not code.
- CDP role/name queries cost 11–35 ms per event (max 64 ms observed live) — no debouncing or batching is needed.
- The recorder reimplements selector ranking itself; Playwright's generator is internal and unavailable as an API.
- Closed shadow roots are unreplayable regardless of capture; XPath never pierces shadow roots; one selector per open shadow-root hop.
- iframes, shadow DOM, and SPA route changes were researched but not exercised by any prototype — implementation slices touching them should budget for surprises.
- Glossary terms this spec leans on: Workflow, Step, Draft, Version, Variable, Step Result, Selector Drift, Re-pick, Artifact.

## Notes

**claude** — 2026-08-12T01:02:03Z

Additive amendment from the execution spec (9gea5p), agreed with the user 2026-08-11. Two fields join this spec's Step document; neither is implemented yet, so both are edits rather than migrations.

1. The Step envelope gains `screenshot?: boolean` (default false) — per-Step screenshot capture. Screenshots are off by default on every Step, including the last one, because a 200-step Workflow would otherwise produce 200 images per Run. A failing Step is screenshotted regardless of the toggle (diagnostics, not preference). The editor renders the toggle in the right-hand badge column beside optional / off / timeout.

2. The `pause-for-takeover` payload gains `successCheck?: Target` — the element whose appearance means the human is done. It reuses this spec's Target shape and the resolve() contract. 4tjwpw's verified hand-back and auto hand-back have nothing to check without it; absent means hand-back stays manual, which is always the case for a heuristic pause.

The execution spec (9gea5p) owns the runtime behavior of both fields; this spec owns their place in the document and the editor.

**claude** — 2026-08-15T04:14:42Z

Edited 2026-08-15: Workflow ownership re-scoped from user to Organization per ADR 0005 (which supersedes ADR 0001). Workflow CRUD and all org-scoped routes carry the X-Organization header per the accounts spec (ufnuvx); the recording-session token stays scoped to one user + one Draft.
