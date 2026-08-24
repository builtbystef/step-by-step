---
id: rjklmp
title: 'Recorder completeness: secrets, downloads, selects, extract, unsupported targets'
state: done
priority: medium
depends_on:
    - disgge
parent: d8ux2s
created: 2026-08-14T06:03:09Z
updated: 2026-08-24T08:52:00Z
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

## Notes

**claude** — 2026-08-17T04:04:21Z

Attended-verification plan (loop operator's decision): the real-Chrome download AC and the debugger-infobar dismissal AC cannot be verified headlessly. Build everything, cover the password/select/extract/unsupported cases in the harness, then apply needs-review with a note naming the two manual checks for the user's attended pass, and do not close.

**agent** — 2026-08-24T08:16:25Z

Implemented recorder completeness at the extension boundary: password values are stripped before selector generation or messaging and carry needsSecret; native option changes emit select Steps; scalar and flat-list extract arming makes the next click side-effect-free; closed-shadow and unreachable-frame targets retain a plain-language unsupported warning shown inline; recent clicks are correlated with chrome.downloads into download Steps; and debugger detach preserves the ended recording buffer for save or discard. Browser fixtures cover password leakage from outside storage/checkpoints, select, scalar/list extract, closed shadow, unreachable frame, and the existing capture pipeline. pnpm check, pnpm test, and the 18-test extension browser tier pass. Attended approval still requires two checks from the issue plan: in real Chrome confirm a clicked download becomes a download Step under the attached debugger, and confirm dismissing the debugger infobar (or opening DevTools) ends recording with prior Steps available to save or discard. Close to approve, or note requested changes and remove needs-review.

**agent** — 2026-08-24T08:52:00Z

Attended pass approved by the user in real Chrome: a clicked extension ZIP became a download Step under the attached debugger; dismissing the debugger bar ended recording with debugger-detached, and every previously captured Step remained preserved in order.
