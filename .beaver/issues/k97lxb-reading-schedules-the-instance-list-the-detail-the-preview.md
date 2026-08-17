---
id: k97lxb
title: 'Reading Schedules: the instance list, the detail, the preview, and run-now'
state: todo
priority: medium
depends_on:
    - 69nls1
parent: nno9gj
created: 2026-08-14T19:51:44Z
updated: 2026-08-17T04:03:37Z
---

## What to build

The read surfaces that make "is anything unattended broken or not firing?" answerable, and the two write actions that belong with them.

```
GET    /api/schedules?workflow_id=&limit=&cursor= → 200 [ScheduleSummary]
GET    /api/workflows/{id}/schedules              → 200 [ScheduleSummary]  (reshaped)
GET    /api/schedules/{id}                        → 200 {schedule, next_occurrences,
                                                          history, last_run}
POST   /api/schedules/preview  {cron, timezone, from?}
                                                  → 200 {next_occurrences: [ts × 5]}
                                                    400 code=invalid_cron | code=invalid_timezone
POST   /api/schedules/{id}/run-now                → 201 {run_id}
                                                    409 code=schedule_run_active {blocking_run_id}
                                                    409 code=needs_values {variable_names}

ScheduleSummary = {
  id, workflow_id, workflow_name, name?, cron, timezone, enabled,
  state: "active" | "paused" | "needs_values",
  missing_variable_names: string[],
  variables: {…},                          // non-secret values only
  next_due_at, last_fired_at,
  last_run: {id, status, failure_reason?, ended_at} | null,
  latest_occurrence: {occurrence_at, reason, blocking_run_id?} | null,
}

HistoryEntry =
  | { kind: "run",        at, run_id, status, failure_reason? }
  | { kind: "occurrence", at, reason: "overlap" | "missed" | "missing_values",
                              blocking_run_id? }
```

The preview is **the only source of Occurrence times in the product** — the server phrases nothing, and the client computes no times. It is stateless and needs no existing Schedule, so the creation form uses it before anything is saved; `from` exists for tests and defaults to now. `run-now` creates a Run with `trigger = schedule` and `schedule_id` set, so it lands in the Schedule's own history; it is **refused while a Run of that Schedule is non-terminal** — the two-copies-never-act-at-once invariant is a safety property, not a default the user can override.

## Acceptance criteria

- [ ] The instance-wide list returns every Schedule the user owns across Workflows, with derived `state`, `missing_variable_names`, `variables`, `last_run`, and `latest_occurrence`; `workflow_id=` scopes it; keyset paging yields distinct ids in order.
- [ ] `GET /api/schedules/{id}` for a Schedule with two Runs and one `overlap` row → three history entries in time order, of both kinds.
- [ ] `POST /api/schedules/preview {cron: "*/7 3-5 * * *", timezone: "UTC"}` → 200 with exactly 5 timestamps; `{cron: "0 9 * * 8"}` → 400 `invalid_cron`; `{timezone: "Mars/Olympus"}` → 400 `invalid_timezone`; it works with no Schedule saved, and `from` makes the timestamps deterministic in tests.
- [ ] `run-now` while a Run of that Schedule is non-terminal → 409 `schedule_run_active` with `blocking_run_id`; after that Run ends → 201, and the new Run appears in the Schedule's history with `trigger = schedule`.
- [ ] `run-now` on a `needs_values` Schedule → 409 `needs_values` naming the Variables.
- [ ] Every route is user-scoped: another user's Schedule id → 404.

## Notes

**claude** — 2026-08-17T04:03:37Z

Re-scope per ADR 0005: 'every Schedule the user owns' reads 'the active Organization's Schedules'; route scoping is the X-Organization Membership gate, so 'another user's Schedule id → 404' reads another Organization's.
