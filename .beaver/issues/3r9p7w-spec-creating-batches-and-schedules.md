---
id: 3r9p7w
title: 'Spec: creating Batches and Schedules'
state: done
assignee: claude
labels:
    - roadmap:idnzwf
    - session:spec
depends_on:
    - tf6796
    - pjxuqx
parent: idnzwf
created: 2026-08-12T01:24:22Z
updated: 2026-08-12T03:43:34Z
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

## Notes

**claude** — 2026-08-12T03:43:34Z

DELIVERABLE — spec issue `nno9gj`, "Creating Batches and Schedules", with blocking edges back to tf6796 and pjxuqx. Seams agreed with the user before drafting: (1) the backend HTTP API, with the scheduler tick invoked directly as a function and an injected `now` — 9gea5p's existing technique; (2) two pure frontend modules called as functions, `reconcile` and the recurrence module, because their computation never reaches the backend and asserting it through the rendered grid would test React rather than the rule.

THE TWO GAPS THE NODE NAMED, SETTLED:

1. NON-FIRING OCCURRENCE RECORD — the fuller fix. `schedules.last_skip_reason` is dropped; a new `schedule_occurrences` table (schedule_id, occurrence_at, reason `overlap`|`missed`|`missing_values`, blocking_run_id?, created_at, unique on schedule+occurrence) records ONLY Occurrences that produced no Run. A fired Occurrence is already the Run carrying that schedule_id, and a second record of it could only disagree. A Schedule's history is those two sources interleaved. Reason for choosing it over the enum-plus-timestamp minimum: one slot on the row can only ever explain the most recent hole, and pjxuqx's occurrence strip is built to show holes older than that. Rows cascade with the Schedule and are pruned to the most recent 500 (a healthy Schedule writes none at all).

2. `variables` ON `schedules` — a JSONB column, non-secret values only, the same rule as runs.variables and batch_rows.variables. 9gea5p's `POST /api/workflows/{id}/schedules` gains `variables` (required, complete) and an optional `name`, and rejects an incomplete set with 400 `missing_variable_values` — pjxuqx's "a Schedule missing a value cannot be saved". A new published Version declaring a Variable the Schedule has no value for STOPS the Schedule rather than firing it blind: the state `needs_values` is DERIVED on read (paused → needs_values → active), never stored, so a publish cannot forget to set a flag; each due Occurrence is recorded `missing_values`, so the Schedule accumulates visible holes instead of going silent; and d8ux2s's publish action warns first, naming the Schedules that will stop. This is deliberately not the Batch answer (tf6796 lets an incomplete row become a `skipped` row), because nobody is watching a Schedule.

ELEVEN FURTHER DECISIONS TAKEN IN THE SAME INTERVIEW (user: "Agree with all the above"): a 120 s grace window past which an Occurrence is `missed` and never run late, with every missed Occurrence getting its own row (capped at 500 per Schedule per tick); the words computed client-side over a closed grammar that declines, the times only ever server-side via a stateless `POST /api/schedules/preview`, so preview and scheduler cannot disagree; a paused Schedule recording nothing at all and recomputing next_due_at on enable, so paused never looks like broken; `POST /api/schedules/{id}/run-now` refused 409 while a Run of that Schedule is non-terminal, keeping 9gea5p's two-copies invariant a safety property rather than an overridable default; an optional Schedule name; `run_incomplete_rows` on the Batch POST, default false; import parsing and reconciliation entirely client-side with normalized-name matching for confidence and near matches offered only as suggestions inside the strip (no alias dictionary); `PATCH /api/batches/{id}/rows/{n}` plus `POST /rows/fill` for filling queued and skipped rows; a 1 000-row cap; a creation-time ETA from the median of the Workflow's last 10 succeeded Runs, shown only with at least 3, blank rather than guessed; and `GET /api/batches?workflow_id=` behind the "copy rows from a past Batch" picker, with no global Batches index.

CROSS-SPEC TOUCHES, all additive and none of the touched specs implemented yet: 9gea5p's RunSummary gains `variables` (what "fill from my last Run" reads); d8ux2s's Workflow read gains `recent_run_median_ms?` (what the ETA multiplies); d8ux2s's publish warns about Schedules it would stop.

GLOSSARY — **Occurrence** added: one moment at which a Schedule was due, whether or not a Run resulted.
