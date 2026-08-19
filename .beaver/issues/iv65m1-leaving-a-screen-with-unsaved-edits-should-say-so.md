---
id: iv65m1
title: Leaving a screen with unsaved edits should say so
state: todo
priority: low
parent: d8ux2s
created: 2026-08-19T20:19:50Z
updated: 2026-08-19T20:19:50Z
---

## What to build

The Draft editor holds an edited copy of the document and sends it when the person saves — nothing saves as you type, because a Draft that saved on every keystroke would be a hundred rejected documents on the way to one good one. The consequence, found while building `y2fsy1`: switching tab, clicking a Workflow in the sidebar, or closing the browser drops the edits without a word. The footer says "Unsaved changes"; nothing stops a person walking past it.

## Acceptance criteria

- [ ] Navigating away from the Editor tab with unsaved edits asks first, and staying keeps every edit.
- [ ] Closing or reloading the browser tab with unsaved edits raises the browser's own warning.
- [ ] Saving, and discarding, both leave nothing to warn about.
- [ ] The decision of where the guard lives is read back without a DOM, the way this frontend's decisions are.
