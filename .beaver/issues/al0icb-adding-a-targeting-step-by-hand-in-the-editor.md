---
id: al0icb
title: Adding a targeting Step by hand in the editor
state: done
assignee: agent
priority: low
depends_on:
    - m6s5me
parent: d8ux2s
created: 2026-08-19T20:19:43Z
updated: 2026-08-29T07:50:15Z
---

## What to build

The editor's add menu offers the three Step types that point at no element — navigate, wait, and pause-for-takeover. The five that need a target (click, type, select, download, extract) are not offered, and a `wait` Step cannot be switched between its duration mode and its element mode, for the same reason: a target needs a verified candidate list, and in `y2fsy1` the editor had no way to produce or write one.

`m6s5me` gives it one — hand-editing a candidate list, and Re-pick through the extension. Once a person can write candidates, adding a targeting Step by hand becomes finishable, and this slice opens the menu.

## Acceptance criteria

- [ ] The add menu offers all eight Step types; a targeting Step added by hand arrives with an empty candidate list and the fragile or unsupported wording that state deserves, never a silent one.
- [ ] A `wait` Step switches between waiting a duration and waiting for an element, and switching to the element mode lands in the same target editor a hand-edit uses.
- [ ] A Step whose target has no candidates at all is refused at publish, or carries a warning the editor makes unmissable — whichever `fq0wr7` and this slice agree on, recorded in a note.

## Notes

**agent** — 2026-08-29T07:50:13Z

Done. The add menu offers all eight Step types; a targeting Step added by hand arrives with an empty candidate list; a wait switches between duration and element.

**Seams.** Spec puts editor UI automation out of scope, so: pure frontend modules read back with no DOM (`steps.ts` — all eight types, `blankStep`, `withWaitMode`; `badges.ts` — empty is not a healthy zero). The add menu already iterates `ADDABLE_STEP_TYPES`, so opening it is that list. The wait form calls `withWaitMode` and lands on the existing selector panel.

**What landed**

- `ADDABLE_STEP_TYPES` is all eight, in spec order. A click / type / select / download / extract added by hand arrives with `{ candidates: [] }` and the amber "no selectors — pick an element" wording, never a silent healthy target.
- `withWaitMode` switches a wait; element mode is that same empty target, so the selector panel is how it is filled. Duration mode starts a one-second pause.
- `WaitPayload` offers the two modes and, for an element, the same selector panel a hand-edit uses.

**Decisions**

- **Publish is not refused.** `fq0wr7`'s modal never inspects targets, and the document store accepts an empty candidate list. This slice agrees: a Step with no candidates carries a warning the editor makes unmissable — the amber "no selectors" badge on the collapsed card, with the same sentence the selector panel already uses — rather than a new publish gate.
- **Empty shares fragile health, not a new state.** Unsupported still outranks it. The badge label and title are the empty wording, not "only position was recorded", because nothing was recorded.
- **Wait still starts as a duration.** One menu entry, two modes in the form.

**For a reviewer**

- `pnpm check` and `pnpm test` green. No DOM test for the add menu or the wait switcher; look at `step-form.tsx` `WaitPayload` against the selector panel `m6s5me` added.
- Health-copy tests pin the spec/m6s5me sentence. `blankStep` tests read the candidate list back, not an internal default.
