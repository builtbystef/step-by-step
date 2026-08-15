---
id: yf7vq2
title: The Schedules list contract and the Batches tab
state: todo
priority: medium
depends_on:
    - 5rkj33
    - vguxj7
    - l88wkp
parent: pc0t8s
created: 2026-08-14T05:55:49Z
updated: 2026-08-14T19:52:50Z
---

## What to build

The remaining two Workflow-scoped lists. The Schedules list is the Batches-and-Schedules spec's table, unchanged — enabled toggle, Workflow, recurrence in words with cron and timezone beneath, next due, last Run outcome, the note column with the most recent non-firing Occurrence, rows expanding in place — and this slice adds only the one-component contract: the same file serves the global route and the Workflow's Schedules tab. The Batches tab lists the Workflow's Batches and is that list's only home, since a global Batches index is refused.

## Acceptance criteria

- [ ] One component renders Schedule rows for both the global route and the Workflow's Schedules tab; a Workflow id prop is its only prop and changes exactly three things — it scopes the request, hides the Workflow column, and swaps the empty state for the Workflow's own call to action. No second file renders Schedule rows.
- [ ] It sits on the same shared cursor-list hook as the Runs list, with filters mirrored into the URL.
- [ ] The global empty state reads "Nothing runs on a clock yet / A Schedule fires a published Workflow on a recurrence you choose, with a value set it owns." with one button to Workflows; a filter matching nothing is a one-line message inside the table.
- [ ] The Workflow's Batches tab lists its Batches from the workflow-scoped batches endpoint, rows navigating to the batch progress screen; no global Batches destination exists anywhere in the nav.
- [ ] A Workflow with no Runs offers Run on its Runs tab and New schedule on its Schedules tab, both disabled behind the one shared sentence while the Workflow is never-published.
