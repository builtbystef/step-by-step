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
updated: 2026-08-12T01:24:22Z
---

Write the spec for the area that turns a Workflow into repeated work: how a Batch and a Schedule are created and read. Everything about how they *execute* is already specified — spec 9gea5p owns the sequential row loop, skip / re-run-a-row / cancel, the batch progress table, the cron engine, skip-on-overlap, and no catch-up. This spec covers only the surfaces and the endpoints that bring these two entities into existence and let a user read them at rest.

Read the notes of the area's closed nodes and their artifacts:

- `tf6796` — the Batch creation verdict: the grid-first page whose columns are the Workflow's Variables, reconciliation-on-import with the mapping strip shown only when it is not confident, the locked secret column, incomplete rows created as `skipped` rows, the sticky footer's counts and ETA, reuse of a past Batch's rows, and the Variables-changed banners. Branch `prototype/batch-creation`.
- `pjxuqx` — the Schedule creation and reading verdict, plus wherever the Variable values for an unattended Run come from.
- `ds8zyn` (the Variable model), `8iuuh8` (secrets never travel in rows; no saved datasets), `9gea5p` (the batch and scheduler halves it already owns), `apx4rs` (the batch progress table).

Interview to close the gaps the two prototypes did not reach, then confirm with the user and invoke the `create-specification` skill. Publish the spec issue with a blocking edge back to each node it covers.
