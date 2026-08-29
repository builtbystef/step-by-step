---
id: 4pxbnx
title: The unsaved-edits guard should also catch the back button
state: todo
priority: low
depends_on:
    - iv65m1
parent: d8ux2s
created: 2026-08-29T07:58:56Z
updated: 2026-08-29T07:58:56Z
---

## What to build

`iv65m1` asks before leaving the Editor via a tab, the sidebar, or closing the browser. It does not catch the browser back button, or `router.push` (the attention band, duplicate, delete). App Router's `popstate` is not cancelable, so staying cannot keep the in-memory copy without lifting it out of the Editor.

## Acceptance criteria

- [ ] Going back (or a programmatic navigation away) with unsaved editor edits asks first, and staying keeps every edit.
- [ ] The decision of how that copy survives an unmount — lifted state, or a history trick — is read back without a DOM, the way this frontend's decisions are.
