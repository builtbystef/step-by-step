---
id: 3r9p7w
title: 'Spec: creating Batches and Schedules'
state: todo
labels:
    - roadmap:idnzwf
    - session:spec
depends_on:
    - tf6796
    - pjxuqx
parent: idnzwf
created: 2026-08-12T01:24:22Z
updated: 2026-08-12T02:15:46Z
---

Write the spec for the area that turns a Workflow into repeated work: how a Batch and a Schedule are created and read. Everything about how they *execute* is already specified — spec 9gea5p owns the sequential row loop, skip / re-run-a-row / cancel, the batch progress table, the cron engine, skip-on-overlap, and no catch-up. This spec covers only the surfaces and the endpoints that bring these two entities into existence and let a user read them at rest.

Read the notes of the area's closed nodes and their artifacts:

- `tf6796` — the Batch creation verdict: the grid-first page whose columns are the Workflow's Variables, reconciliation-on-import with the mapping strip shown only when it is not confident, the locked secret column, incomplete rows created as `skipped` rows, the sticky footer's counts and ETA, reuse of a past Batch's rows, and the Variables-changed banners. Branch `prototype/batch-creation`.
- `pjxuqx` — the Schedule creation and reading verdict: the sentence builder with preset chips and always-visible generated cron, readback in words plus real occurrences (declining to phrase what it cannot), the timezone rule, one all-Schedules table with rows expanding in place as the primary at-rest surface, the three devices that keep a missing Run from being a mystery, and — the answer to where an unattended Run's Variables come from — a value set owned by the Schedule, entered in the Batch grid with one row. Branch `prototype/schedule-creation`.
- `ds8zyn` (the Variable model), `8iuuh8` (secrets never travel in rows; no saved datasets), `9gea5p` (the batch and scheduler halves it already owns), `apx4rs` (the batch progress table).

Two things this spec must settle that its inputs deliberately left open:

1. **The non-firing-occurrence record.** Spec 9gea5p gives `schedules` a single `last_skip_reason` slot, but the surface `pjxuqx` settled has to tell two different stories — *the previous Run was still running* and *the instance was not running* — and its occurrence strip wants holes older than the most recent one. Minimum: an enum plus `last_skip_at`. Fuller: persist non-firing occurrences as rows so occurrence history is uniform with Runs. Decide, and say why.
2. **The `variables` column on `schedules`**, its interaction with 9gea5p's `POST /api/workflows/{id}/schedules` contract, and what happens to a Schedule when a new published Version declares a Variable it has no value for (`tf6796` settled the Batch half of that question; the Schedule half is unattended, so it is not the same answer).

Interview to close the remaining gaps, then confirm with the user and invoke the `create-specification` skill. Publish the spec issue with a blocking edge back to each node it covers.
