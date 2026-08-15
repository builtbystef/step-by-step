---
id: 5rkj33
title: The Workflows list, the Workflow CRUD contract, and the Workflow page
state: todo
priority: medium
depends_on:
    - hat4cf
    - sl7h4j
    - g795ji
parent: pc0t8s
created: 2026-08-14T05:55:09Z
updated: 2026-08-14T06:04:25Z
---

## What to build

The screen a user lands on, and the routes no other spec defines. List, create, rename, duplicate, and delete for Workflows — additive to the recording spec, which keeps every Draft and Version behavior it owns — plus the Workflow detail page: a header with the name, the draft-state chip, and a Run action, over four linkable tabs (Editor default, Runs, Schedules, Batches; the tab contents beyond Editor arrive with later slices). The list's Run-derived and Schedule-derived columns, the delete guard against a live Run, and the cascade over Runs and Schedules belong to a follow-up slice, once those objects exist — this slice computes what the Workflow/Draft/Version ground provides.

## Acceptance criteria

- [ ] The list endpoint returns Workflow summaries (id, name, created and last-activity times, draft state, published version when one exists, schedule and run fields as the data allows) and supports `q`, three sorts, and keyset cursor paging: sorted by name with page size 10 over 25 Workflows, paging to exhaustion yields 25 distinct ids in name order with none seen twice, stable while rows change underneath.
- [ ] `q=acme` matches names case-insensitively; sort defaults to activity; a never-run Workflow orders by its own updated time.
- [ ] Create with a name → 201; rename → 200; duplicate → 201 where every Step id differs from the source, order and payloads match, and the copy's draft state is never-published.
- [ ] Delete → 204 and the Workflow's Drafts and Versions are gone; the confirm dialog names what goes with it and is plain confirm, not type-to-confirm — that ceremony stays reserved for account deletion.
- [ ] A Workflow with no published Version reports draft state never-published with no published version, and starting it is refused with a machine-readable no-published-version code, rendered everywhere as the one shared sentence.
- [ ] The row: name as primary; a meta line with the last Run's status chip and relative time (or "never run") and the schedule indicator when data exists; the draft-state badge on the right (neutral never-published, amber unpublished changes, green in-sync-with-version); hover actions — inline Run, and an overflow with New batch, New schedule, Duplicate, Rename, Delete. Run, New batch, and New schedule are disabled behind the shared sentence while never-published; row click opens the editor tab.
- [ ] The search box and sort control render only at 40 rows or more; the endpoint always supports both.
- [ ] New workflow is a primary button opening a name-only dialog and landing on the empty Editor tab.
- [ ] The Workflow page header shows name, draft-state chip, a Run action available from every tab, and an overflow repeating the row actions; the four tabs are each their own URL, the bare Workflow path redirects to the editor tab, and the back button walks tabs.
- [ ] HTTP seam tests with a real Postgres cover the paging, search, sort, duplicate, delete, and never-published examples.
