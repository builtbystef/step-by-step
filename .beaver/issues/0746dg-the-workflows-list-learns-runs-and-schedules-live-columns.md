---
id: 0746dg
title: 'The Workflows list learns Runs and Schedules: live columns, delete guard, full cascade'
state: todo
priority: medium
depends_on:
    - 5rkj33
    - 423dg6
    - g461z0
    - e2q15g
parent: pc0t8s
created: 2026-08-14T05:56:15Z
updated: 2026-08-14T19:52:50Z
---

## What to build

The Workflow summary's Run-derived and Schedule-derived behavior, deferred from the list slice until those objects exist. The list row's meta line goes live, activity sort follows real Runs, and Workflow deletion gains its guard and its full blast radius: the confirm dialog names the real counts, a live Run refuses the delete, and the cascade takes Schedules, Batches, Runs, Step Results, and Artifacts with it.

## Acceptance criteria

- [ ] The summary carries the last Run (id, status, finished time), the schedule count with the single-schedule label (e.g. "weekdays 09:00"), and the recent-run median duration; the row's meta line renders the last Run's status chip with its relative time and the schedule indicator ("weekdays 09:00", or "3 schedules").
- [ ] Activity sort uses the latest Run's creation time: the Workflow whose Run started most recently sorts first, and a never-run Workflow still orders by its own updated time.
- [ ] Deleting a Workflow with 2 Schedules and 42 Runs → 204, and the Schedules, Batches, Runs, Step Results, and the Runs' Artifacts are gone — Artifacts verified by observing the object store; the confirm dialog names the counts ("3 Schedules and 42 Runs will be deleted").
- [ ] Deleting while a Run of the Workflow is non-terminal → 409 with a machine-readable run-active code, surfaced in the dialog; the delete succeeds once the Run reaches a terminal state.
- [ ] HTTP seam tests with a real Postgres cover the summary fields, the activity ordering, the guard, and the full cascade.
