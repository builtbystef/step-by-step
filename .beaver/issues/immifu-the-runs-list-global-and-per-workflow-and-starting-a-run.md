---
id: immifu
title: The Runs list, global and per-Workflow, and starting a Run from the list
state: todo
priority: medium
depends_on:
    - 5rkj33
    - 423dg6
    - bcyznn
parent: pc0t8s
created: 2026-08-14T05:55:39Z
updated: 2026-08-14T19:52:50Z
---

## What to build

One reverse-chronological answer to "what happened lately, and what is running now?" — a single Runs list component serving both the global screen and the Workflow's Runs tab, on a shared cursor-list hook over the runs endpoint. The Workflow-scoped variant differs in exactly three ways. This slice also makes the Run actions on the Workflows list and the Workflow header real: an immediate start when the Workflow declares no Variables, and the one-row value grid when it declares some.

## Acceptance criteria

- [ ] One component renders Run rows for both the global route and the Workflow's Runs tab; a Workflow id prop is its only prop and changes exactly three things — it scopes the request, hides the Workflow column, and swaps the empty state for the Workflow's own call to action. No second file renders Run rows; that is the reviewable form of the rule.
- [ ] Both lists sit on one shared cursor-list hook (an infinite-query wrapper) owning page size, Load more, and mirroring filter state into the URL — a filtered list is linkable and survives a reload; its query key is what mutations invalidate.
- [ ] Columns: status chip, Workflow, trigger, started (relative), duration, the Run id in monospace, and a right-hand cell that is Take control for a waiting Run and a chevron otherwise; filters are status and trigger (manual, schedule, batch, test); sort is reverse-chronological and not user-controllable; rows navigate to the run detail — never expand in place.
- [ ] The inline Run action and the header Run action start a Run immediately and navigate to it when the Workflow declares no Variables; when it declares some, they open the one-row value grid — secret Variables rendered as the locked cell — and start from there.
- [ ] The global empty state reads "Nothing has run yet / Runs appear here whether you start them by hand, on a schedule, or as a batch." with one button to Workflows; a filter matching nothing is a one-line message inside the table, never the empty state.
- [ ] The list refreshes on navigation, filter change, and Load more only — no polling and no push; starting or cancelling a Run invalidates both this list and the attention query.
