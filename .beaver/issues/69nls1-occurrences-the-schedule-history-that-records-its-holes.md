---
id: 69nls1
title: 'Occurrences: the Schedule history that records its holes'
state: done
assignee: agent
priority: high
depends_on:
    - fpzupm
parent: nno9gj
created: 2026-08-14T19:51:44Z
updated: 2026-08-25T17:41:24Z
---

## What to build

A Schedule's failures are silences; this slice makes every silence a row. The `schedule_occurrences` table: `schedule_id`, `occurrence_at`, `reason` (`overlap` | `missed` | `missing_values`), `blocking_run_id` (nullable, set for `overlap`), `created_at`, unique on `(schedule_id, occurrence_at)`. It records **only Occurrences that produced no Run** — a fired Occurrence is already recorded as the Run carrying that `schedule_id`, and a second record could only disagree. Rows are cascade-deleted with their Schedule, and the tick prunes each Schedule to its most recent 500 rows.

The scheduler tick's firing steps are reworked for each due, enabled Schedule of a non-disabled user:

1. **Missing values first**: if the latest published Version declares a non-secret Variable absent from the Schedule's values, record `missing_values` and advance — no Run, and `next_due_at` keeps moving so the holes accumulate visibly rather than the Schedule going silent.
2. **Lateness**: enumerate every Occurrence from `next_due_at` up to now; each more than the 120-second grace window late is recorded `missed` and never run. At most 500 rows are written per Schedule per tick; a longer outage records the 500 most recent and moves on. Only an Occurrence within the grace window may fire.
3. **Overlap**: a still-non-terminal Run of this Schedule → record `overlap` with `blocking_run_id`, create nothing.
4. **Fire**: a Run of the latest published Version, `trigger = schedule`, `schedule_id` set, `variables` copied; enqueue.
5. Advance `next_due_at` to the first Occurrence strictly after the one handled, computed by croniter in the Schedule's IANA timezone.

`last_skip_reason` is dropped from the table and from every read — this table replaces it. **Paused Schedules record nothing**: disabling sets `next_due_at` to null, enabling recomputes it from now, and a disabled user's Schedules behave the same way. The grace window (120 s) and the prune depth (500) are named constants in one place.

## Acceptance criteria

The tick is invoked directly as a function with an injected now; effects are asserted over HTTP. Cron `0 9 * * *` in `Europe/Belgrade` unless stated.

- [ ] Tick at 09:00:45 with `next_due_at` = 09:00 → one Run created (`trigger = schedule`, `variables` equal to the Schedule's), zero Occurrence rows, `next_due_at` = tomorrow 09:00 local time.
- [ ] Tick at 09:04:00 with `next_due_at` = 09:00 → no Run; one row, reason `missed`; `next_due_at` = tomorrow 09:00.
- [ ] `0 * * * *` with `next_due_at` six hours in the past → six rows, all `missed`, zero Runs, `next_due_at` the next future hour.
- [ ] The previous Run still `running` at the next Occurrence → no Run; one row, reason `overlap`, `blocking_run_id` = that Run.
- [ ] A `needs_values` Schedule at its Occurrence → one row, reason `missing_values`, no Run, `next_due_at` advanced; supplying the value → the following tick fires.
- [ ] Across the October DST change, 09:00 `Europe/Belgrade` fires at 07:00Z and then at 08:00Z.
- [ ] Disable a Schedule, pass three Occurrences, enable → zero Occurrence rows written, `next_due_at` in the future. A disabled user's enabled Schedule behaves the same.
- [ ] A Schedule accumulating more than 500 rows is pruned to its most recent 500.
- [ ] `last_skip_reason` is gone from the schema and from every response that carried it.
- [ ] Deleting a Schedule deletes its Occurrence rows.

## Notes

**claude** — 2026-08-17T04:03:37Z

Re-scope per ADR 0005: the tick enumerates each due, enabled Schedule of the (org-owned) table — the 'of a non-disabled user' condition and the 'disabled user's enabled Schedule' AC are dropped; per-user disable no longer exists. Everything else unchanged.

**agent** — 2026-08-25T17:31:02Z

Seam (from the spec's Testing Decisions): tick() is invoked directly with clock.now() frozen; Runs, next_due_at, last_fired_at, and latest_occurrence are asserted over HTTP. Multi-row Occurrence counts (six missed hours, the 500-row prune, cascade-on-delete) are observed on the table — GET /api/schedules/{id} history is k97lxb. latest_occurrence replaces last_skip_reason on the existing Schedule CRUD so a hole's reason is visible at this slice's HTTP surface. The dropped 'disabled user' AC is not built (ADR 0005 note).

**agent** — 2026-08-25T17:41:24Z

Completed Occurrences: holes are rows, last_skip_reason is gone.

Seam: tick() with clock.now() frozen; Runs, next_due_at, last_fired_at, and latest_occurrence over HTTP. Multi-row counts (six missed hours, the 500 prune, cascade-on-delete) observed on the table — GET /api/schedules/{id} history is k97lxb.

What landed:
- schedule_occurrences (schedule_id, occurrence_at, reason overlap|missed|missing_values, blocking_run_id, created_at), unique on (schedule_id, occurrence_at), cascade-deleted with the Schedule.
- Tick walks each due enabled Schedule from next_due_at through now. Missing values write missing_values and advance. Occurrences more than GRACE_WINDOW_SECONDS (120) late are missed. A non-terminal Run writes overlap with blocking_run_id. Only an in-grace Occurrence fires (latest published Version, trigger=schedule, variables copied). At most OCCURRENCE_PRUNE_DEPTH (500) rows per Schedule per tick; the table is then pruned to that Schedule's most recent 500.
- last_skip_reason dropped from the schema and every response. latest_occurrence replaces it on create/list/patch.
- Disabling sets next_due_at to null; enabling recomputes from now. Paused Schedules write no holes.
- The dropped 'disabled user' AC was not built (ADR 0005).
