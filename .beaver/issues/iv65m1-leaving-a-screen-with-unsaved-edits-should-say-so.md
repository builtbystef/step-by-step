---
id: iv65m1
title: Leaving a screen with unsaved edits should say so
state: done
assignee: agent
priority: low
parent: d8ux2s
created: 2026-08-19T20:19:50Z
updated: 2026-08-29T07:58:56Z
---

## What to build

The Draft editor holds an edited copy of the document and sends it when the person saves — nothing saves as you type, because a Draft that saved on every keystroke would be a hundred rejected documents on the way to one good one. The consequence, found while building `y2fsy1`: switching tab, clicking a Workflow in the sidebar, or closing the browser drops the edits without a word. The footer says "Unsaved changes"; nothing stops a person walking past it.

## Acceptance criteria

- [ ] Navigating away from the Editor tab with unsaved edits asks first, and staying keeps every edit.
- [ ] Closing or reloading the browser tab with unsaved edits raises the browser's own warning.
- [ ] Saving, and discarding, both leave nothing to warn about.
- [ ] The decision of where the guard lives is read back without a DOM, the way this frontend's decisions are.

## Notes

**agent** — 2026-08-29T07:58:46Z

Done. Leaving the Editor with unsaved edits asks first; staying keeps every edit; a save or a discard leaves nothing to warn about.

**Seam.** The spec rules editor UI automation out, so the outermost seam that can observe the criteria without a DOM is the pure decision of where the guard lives — `leave.ts`, read back the way this frontend's other decisions are. Five Vitest tests. The click intercept and `beforeunload` listener are glue on the Editor page.

**What landed**

- `leave.ts` — `shouldAskBeforeLeave(unsaved, from, to)`. `to` is `null` for close/reload. The guard lives on the Editor tab: another tab, another Workflow, or the sidebar all ask; a Version of the same Workflow, or the bare address that redirects here, do not. Saving and discarding clear the edited copy (`edited === null`), so the same table says there is nothing to warn about.
- The Editor page arms `beforeunload` (the browser's own warning) and a capture-phase click listener while the copy is dirty. Staying is `preventDefault`, so the edited copy never unmounts.

**Deliberately not here**

- The browser back button, and `router.push` (the attention band, duplicate, delete). App Router's `popstate` is not cancelable, so staying cannot keep the in-memory copy without lifting it out of the Editor. The named cases — switching tab, the sidebar, closing the browser — are Link clicks and unload.

**For a reviewer**

- `pnpm check` and `pnpm test` green (539).
- No DOM test exists for the confirm or the browser warning; what a reviewer should look at by eye is the capture-phase listener in `page.tsx` against a dirty Editor.
