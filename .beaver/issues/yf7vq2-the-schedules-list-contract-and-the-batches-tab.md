---
id: yf7vq2
title: The Schedules list contract and the Batches tab
state: done
assignee: agent
priority: medium
depends_on:
    - 5rkj33
    - vguxj7
    - l88wkp
parent: pc0t8s
created: 2026-08-14T05:55:49Z
updated: 2026-08-26T23:49:07Z
---

## What to build

The remaining two Workflow-scoped lists. The Schedules list is the Batches-and-Schedules spec's table, unchanged — enabled toggle, Workflow, recurrence in words with cron and timezone beneath, next due, last Run outcome, the note column with the most recent non-firing Occurrence, rows expanding in place — and this slice adds only the one-component contract: the same file serves the global route and the Workflow's Schedules tab. The Batches tab lists the Workflow's Batches and is that list's only home, since a global Batches index is refused.

## Acceptance criteria

- [ ] One component renders Schedule rows for both the global route and the Workflow's Schedules tab; a Workflow id prop is its only prop and changes exactly three things — it scopes the request, hides the Workflow column, and swaps the empty state for the Workflow's own call to action. No second file renders Schedule rows.
- [ ] It sits on the same shared cursor-list hook as the Runs list, with filters mirrored into the URL.
- [ ] The global empty state reads "Nothing runs on a clock yet / A Schedule fires a published Workflow on a recurrence you choose, with a value set it owns." with one button to Workflows; a filter matching nothing is a one-line message inside the table.
- [ ] The Workflow's Batches tab lists its Batches from the workflow-scoped batches endpoint, rows navigating to the batch progress screen; no global Batches destination exists anywhere in the nav.
- [ ] A Workflow with no Runs offers Run on its Runs tab and New schedule on its Schedules tab, both disabled behind the one shared sentence while the Workflow is never-published.

## Notes

**agent** — 2026-08-26T23:18:35Z

Seam (AFK): the parent spec names seam 1 (HTTP) and seam 2 (resolveGate) only, and rules out component/DOM tests. The lists' workflowId rule is three lines of conditional rendering. Following the Runs list (immifu) and the Schedules table (l88wkp), the outermost seam that can observe the acceptance criteria is pure functions without a DOM — presentation.ts for what a Workflow id changes, the empty states, and where a Batch row goes. The pages draw those functions.

**agent** — 2026-08-26T23:49:07Z

Completed the Schedules list contract and the Workflow Batches tab.

Seam (AFK, recorded earlier): pure functions without a DOM. The pages draw them.

What landed
- One `SchedulesList` (`schedules-list.tsx`) renders Schedule rows for `/schedules` and `/workflows/[id]/schedules`. `workflowId` is its only prop and changes exactly three things: it scopes `GET /api/schedules?workflow_id=`, hides the Workflow column, and swaps the empty state. `schedules-table.tsx` is gone — no second file renders Schedule rows.
- Both variants sit on `useCursorList`, same hook as the Runs list, with filters mirrored into the URL.
- Global empty state is the spec's sentence, with one button to Workflows. A filter matching nothing is a one-line message inside the table. The Workflow tab's empty state offers New schedule.
- The Batches tab lists `GET /api/batches?workflow_id=` via the same cursor hook; rows navigate to `/batches/{id}`. The nav still has no Batches destination.
- New schedule (Schedules tab) and Run (Runs tab, already there) are disabled behind `COPY.noPublishedVersion` while never-published. New batch on the empty Batches tab uses the same sentence.

Decisions
- Workflow-scoped empty copy was not pinned: "This Workflow has no Schedule yet" / New schedule, and "This Workflow has no Batch yet" / New batch.
- The list uses `listAllSchedules` (cursor + optional workflow_id) rather than the unpaged `listSchedules`, so both routes are one hook.
- A Batch row shows name, created, and row count. No invented Batch-level lifecycle state — StatusChip is for Runs, Occurrences, and Batch *rows*.
- `NEW_BATCH` and `NEW_SCHEDULE` are named exports of the same action objects the overflow already offered, so an empty tab cannot drift from the header.

For a reviewer
- `presentation.test.ts` on both lists covers every acceptance criterion the spec allows without a DOM.
- Visual language scan still holds.
