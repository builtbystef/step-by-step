---
id: al0icb
title: Adding a targeting Step by hand in the editor
state: todo
priority: low
depends_on:
    - m6s5me
parent: d8ux2s
created: 2026-08-19T20:19:43Z
updated: 2026-08-19T20:19:43Z
---

## What to build

The editor's add menu offers the three Step types that point at no element — navigate, wait, and pause-for-takeover. The five that need a target (click, type, select, download, extract) are not offered, and a `wait` Step cannot be switched between its duration mode and its element mode, for the same reason: a target needs a verified candidate list, and in `y2fsy1` the editor had no way to produce or write one.

`m6s5me` gives it one — hand-editing a candidate list, and Re-pick through the extension. Once a person can write candidates, adding a targeting Step by hand becomes finishable, and this slice opens the menu.

## Acceptance criteria

- [ ] The add menu offers all eight Step types; a targeting Step added by hand arrives with an empty candidate list and the fragile or unsupported wording that state deserves, never a silent one.
- [ ] A `wait` Step switches between waiting a duration and waiting for an element, and switching to the element mode lands in the same target editor a hand-edit uses.
- [ ] A Step whose target has no candidates at all is refused at publish, or carries a warning the editor makes unmissable — whichever `fq0wr7` and this slice agree on, recorded in a note.
