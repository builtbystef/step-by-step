---
id: fq0wr7
title: 'Editor: versions, publish with diff, and restore'
state: todo
priority: medium
depends_on:
    - g795ji
    - y2fsy1
parent: d8ux2s
created: 2026-08-14T06:04:08Z
updated: 2026-08-14T06:04:08Z
---

## What to build

The editor's version surface over the publish machinery. The header carries the Draft chip and a version dropdown; past Versions open read-only with a restore path; publishing walks through a modal that shows the step-level diff before minting.

## Acceptance criteria

- [ ] The header shows the Draft chip — amber "unpublished changes", green "in sync with vN" — driven by the derived draft state, and the version dropdown lists the Draft plus every Version.
- [ ] Selecting a past Version opens it read-only (no card edits, no drawer edits) with a restore-to-Draft action; restoring loads that Version's document into the Draft and returns to editing, with the chip reflecting the new comparison.
- [ ] Publish opens a modal rendering the step-level diff against the last Version — added, removed, and changed Steps by their labels — and confirming mints the next Version and flips the chip to in-sync; a first publish (no prior Version) shows every Step as added.
- [ ] Cancelling the modal mints nothing.
