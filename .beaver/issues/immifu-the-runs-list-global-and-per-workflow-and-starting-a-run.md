---
id: immifu
title: The Runs list, global and per-Workflow, and starting a Run from the list
state: done
assignee: agent
priority: medium
depends_on:
    - 5rkj33
    - 423dg6
    - bcyznn
parent: pc0t8s
created: 2026-08-14T05:55:39Z
updated: 2026-08-26T23:12:40Z
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

## Notes

**agent** — 2026-08-26T23:12:35Z

Done. The Runs list — one component for /runs and the Workflow's Runs tab — and the Run action on the Workflows list and the Workflow header.

Seams (as the spec's Testing Decisions name them, and as an AFK session taking the established frontend seam): no component or DOM tests. Pure functions without a DOM — lib/cursor-list.ts (page size, query key, URL-mirrored filters), runs/presentation.ts (what a Workflow id changes, empty vs filtered-empty, Take control vs chevron, duration), workflows/start-run.ts (immediate vs the one-row grid, a payload that never carries a secret). Additive HTTP coverage for the two list fields this screen needed: workflow_name on RunSummary, and a trigger filter on GET /api/runs.

What landed
- RunsList — one file of rows. workflowId is the only prop and changes exactly three things: it scopes the request, hides the Workflow column, and swaps the empty state. /runs and /workflows/[id]/runs both mount it.
- useCursorList — the shared infinite-query wrapper. Owns page size 25, Load more, and mirroring status/trigger into the URL so a filtered list is linkable and survives a reload. Query key is [path, orgId, filters]; orgId is in it so switching Organizations cannot serve the previous tenant's page. The path is RUNS_KEY (["/api/runs"]), so invalidateRunState still prefix-invalidates every filter. No polling, no refetch-on-focus.
- Starting a Run: immediate when the published Version declares no Variables; the one-row ValueGrid (secret Variables locked, never sent) when it declares some. The list row, the header, and the Workflow-scoped empty state share useStartRun. Starting invalidates the Runs list and the attention query together, then navigates to /runs/{id}.
- GET /api/runs now joins the Workflow name onto each summary and accepts trigger= next to status= and workflow_id=.

Decisions
- workflow_name and trigger on the list endpoint. The spec said RunSummary carries the fields this screen renders, and the issue's filters include trigger. 423dg6 built the store without either; this slice is the first consumer. Duration is computed on the client from started_at/ended_at (or now while running) rather than stored.
- Started column uses started_at, falling back to queued_at. A queued Run has not been claimed; showing when it was asked to start is still a time, not a blank.
- A Workflow id is a route, not a URL filter. Status and trigger are mirrored; workflow_id is in the query key and the request, never in the address the tab already names.
- Empty vs filtered-empty keys off status/trigger, not scope. A Workflow with no Runs is the empty state with Run; /runs?status=failed matching nothing is the one-line table message.

For a reviewer
- No second file renders Run rows: runs-list.tsx is the only map over them.
- waiting_for_human in the status filter is worded "needs you", matching the chip, without calling lifecycleLabel (that identifier is reserved for StatusChip).
- Secret omission on start is asserted on startBody, the same way the Batch grid asserts it on createBody.
