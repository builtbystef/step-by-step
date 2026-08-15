---
id: g461z0
title: 'The scheduler: cron, timezones, overlap skip, no catch-up'
state: todo
priority: medium
depends_on:
    - 423dg6
parent: 9gea5p
created: 2026-08-14T07:42:22Z
updated: 2026-08-14T07:42:34Z
---

## What to build

The `schedules` table (workflow, user, cron, IANA timezone, enabled, last_fired_at, next_due_at, last_skip_reason) and the engine's semantics. Cron parsing and next-occurrence computation use croniter; timezone handling is the standard library's zoneinfo — no other scheduling library, no task framework. The minute loop — one directly-invokable tick function, shared with the reaping duties whichever slice lands it first — fires each enabled Schedule whose occurrence has passed by creating a Run of the Workflow's latest published Version (`trigger` = `schedule`) and enqueueing it.

Two copies of one Workflow never act on a site at once: if a Run from that same Schedule is still non-terminal, the occurrence is skipped and `last_skip_reason` records it. Missed occurrences are skipped entirely, never caught up — an instance down all night does not fire six 09:00 Runs when it returns; `next_due_at` moves to the next future occurrence. A disabled user's Schedules do not fire. The CRUD contract (the editing UI is another spec's):

```
GET    /api/workflows/{id}/schedules → 200 [{id, cron, timezone, enabled,
                                             last_fired_at, next_due_at, last_skip_reason}]
POST   /api/workflows/{id}/schedules {cron, timezone, enabled} → 201
                                       400 code=invalid_cron | code=invalid_timezone
PATCH  /api/schedules/{id}           {cron?, timezone?, enabled?} → 200
DELETE /api/schedules/{id}           → 204
```

## Acceptance criteria

- [ ] Two ticks a minute apart across 09:00 for a Schedule with `0 9 * * *` in `Europe/Belgrade` → exactly one Run created, `trigger` = `schedule`, and `next_due_at` is tomorrow 09:00 local time, not UTC.
- [ ] A Schedule whose previous Run is still `running`, then a tick at the next occurrence → no Run created, `last_skip_reason` = overlap, `next_due_at` advanced.
- [ ] A tick after a six-hour gap covering three missed occurrences → zero catch-up Runs, and `next_due_at` is in the future.
- [ ] A disabled Schedule never fires; re-enabling resumes from the next future occurrence, not the missed ones.
- [ ] A disabled user's enabled Schedule does not fire.
- [ ] `POST` with cron `not a cron` → 400 `invalid_cron`; with timezone `Mars/Olympus` → 400 `invalid_timezone`.
- [ ] The fired Run executes the latest published Version at fire time, not the Version that existed when the Schedule was created.
- [ ] Schedule routes are user-scoped: another user's Schedule id → 404.

