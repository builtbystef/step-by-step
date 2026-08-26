---
id: 0746dg
title: 'The Workflows list learns Runs and Schedules: live columns, delete guard, full cascade'
state: done
assignee: agent
priority: medium
depends_on:
    - 5rkj33
    - 423dg6
    - g461z0
    - e2q15g
parent: pc0t8s
created: 2026-08-14T05:56:15Z
updated: 2026-08-26T13:20:24Z
---

## What to build

The Workflow summary's Run-derived and Schedule-derived behavior, deferred from the list slice until those objects exist. The list row's meta line goes live, activity sort follows real Runs, and Workflow deletion gains its guard and its full blast radius: the confirm dialog names the real counts, a live Run refuses the delete, and the cascade takes Schedules, Batches, Runs, Step Results, and Artifacts with it.

## Acceptance criteria

- [ ] The summary carries the last Run (id, status, finished time), the schedule count with the single-schedule label (e.g. "weekdays 09:00"), and the recent-run median duration; the row's meta line renders the last Run's status chip with its relative time and the schedule indicator ("weekdays 09:00", or "3 schedules").
- [ ] Activity sort uses the latest Run's creation time: the Workflow whose Run started most recently sorts first, and a never-run Workflow still orders by its own updated time.
- [ ] Deleting a Workflow with 2 Schedules and 42 Runs → 204, and the Schedules, Batches, Runs, Step Results, and the Runs' Artifacts are gone — Artifacts verified by observing the object store; the confirm dialog names the counts ("3 Schedules and 42 Runs will be deleted").
- [ ] Deleting while a Run of the Workflow is non-terminal → 409 with a machine-readable run-active code, surfaced in the dialog; the delete succeeds once the Run reaches a terminal state.
- [ ] HTTP seam tests with a real Postgres cover the summary fields, the activity ordering, the guard, and the full cascade.

## Notes

**agent** — 2026-08-26T13:20:24Z

Done. The Workflows list's Run-derived and Schedule-derived columns, the activity sort, the live-Run delete guard, and the full cascade.

Seams (as the spec's Testing Decisions name them): HTTP against the FastAPI app with a real Postgres (and Garage, for the Artifact purge). Frontend decisions in messages.ts are read back as functions with no DOM.

What landed
- WorkflowSummary now carries last_run (id, status, finished_at), schedule_count, schedule_label when there is exactly one, recent_run_median_ms (median of the last ten succeeded Runs, absent below three), and run_count (what the delete dialog names). A page of rows is hydrated after the name query, so the list still travels as a page of names.
- Activity is GREATEST of the Workflow stamp, the Draft stamp, and the newest Run's queued_at. Postgres GREATEST is null if any argument is, so a never-run Workflow coalesces the missing Run time onto a stamp it already has.
- DELETE /api/workflows/{id} is 409 run_active while any Run of the Workflow is non-terminal. Otherwise it purges the Runs' Garage objects and lets the foreign keys take Schedules, Batches, Runs, Step Results, and Artifact rows.
- The list row's meta line draws the last Run through StatusChip and relativeTime, and the schedule indicator (weekdays 09:00, or 3 schedules). The delete dialog names the counts (3 Schedules and 42 Runs will be deleted) and surfaces run_active.

Decisions
- finished_at is omitted while the last Run is still live, matching the list's exclude_none convention (same as published_version on a never-published Workflow). The spec type allows null; absence is how this API says that.
- run_count is on the summary. The spec's WorkflowSummary type did not name it, but the confirm dialog has to name the counts and a second request would be a second truth. schedule_count was already there for the same reason.
- The single-schedule label is a compact readback of the closed recurrence grammar (weekdays 09:00 for 0 9 * * 1-5), produced on the backend because the field lives on WorkflowSummary. An expression outside the grammar is sent through as the cron itself.
- Median duration is wall-clock (ended_at - (started_at or queued_at)), the same interval Batch ETA already uses.

For a reviewer
- The cascade test seeds 2 Schedules, a Batch, 42 terminal Runs, a Step Result, and a Garage object, then observes the object store after the 204.
- Tenancy of delete is unchanged: another Organization's Workflow is still 404.
