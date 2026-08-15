---
id: rjklmp
title: 'Recorder completeness: secrets, downloads, selects, extract, unsupported targets'
state: todo
priority: medium
depends_on:
    - disgge
parent: d8ux2s
created: 2026-08-14T06:03:09Z
updated: 2026-08-14T06:03:09Z
---

## What to build

The remaining capture behaviors, including the two safety promises: a recorded password never lands anywhere, and anything the tool cannot replay is flagged the moment it is captured, in plain language. Download clicks correlate to their file; selects and extraction get their step types; a dismissed debugger infobar ends the recording gracefully. iframes and shadow DOM were researched but never prototyped — budget for surprises.

## Acceptance criteria

- [ ] Typing into a password field emits a type Step with an empty value and a needs-secret marker, and the literal typed value appears nowhere in any emitted message — not in checkpoints, not between extension contexts; asserted from outside.
- [ ] A click that produces a file download, correlated within a time window, emits a download Step (exercised in a real Chrome session — download events behave differently under an attached debugger).
- [ ] Choosing an option emits a select Step (driven via option selection in the harness — native select popups misbehave under the debugger).
- [ ] With the extract toggle armed, the next click is side-effect-free and emits an extract Step carrying the captured text and selectors; scalar mode names one value (text or attribute), list mode yields flat records of sub-selector fields.
- [ ] A target inside a closed shadow root, or in a frame the extension cannot inject into, triggers an immediate inline warning in plain, non-technical language; recording never blocks, and the Step permanently carries the unsupported flag with that warning text.
- [ ] Dismissing the debugger infobar (or opening DevTools) ends the recording while keeping every Step captured so far; the user may save or discard.
- [ ] Extension-boundary tests cover the password, select, extract, unsupported, and infobar cases on fixture pages; the download case is verified in a real Chrome session.
