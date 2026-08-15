---
id: vguxj7
title: 'Batch rows arrive imperfect: skipped rows, limits, row edits, and fill'
state: todo
priority: high
depends_on:
    - 297ba3
parent: nno9gj
created: 2026-08-14T19:51:01Z
updated: 2026-08-14T19:51:01Z
---

## What to build

The API surface that lets a Batch be born from somebody else's spreadsheet without losing the file to three bad rows. `POST /api/workflows/{id}/batches` gains `run_incomplete_rows?: bool = false`: a row missing a value for a declared non-secret Variable is created as a `skipped` row rather than discarded — the execution side already knows how to show it and re-run it. `true` creates it `queued`, because an empty Variable is legitimate when the Step referencing it is optional or disabled. The endpoint also gains its refusals: `400 code=unknown_variable {names}`, `413 code=too_many_rows {max: 1000}`, `409 code=no_published_version`. The row cap is a named constant, not a literal.

New endpoints:

```
GET    /api/batches?workflow_id=&limit=&cursor=   → 200 [BatchSummary]
PATCH  /api/batches/{id}/rows/{n}   {variables}   → 200 {row}
                                                    409 code=row_not_editable
POST   /api/batches/{id}/rows/fill  {name, value} → 200 {updated_count}

BatchSummary = { id, name, workflow_id, created_at, cancelled_at,
                 row_count, stats: {succeeded, failed, queued, skipped, cancelled} }
```

`PATCH` accepts a row in `queued`, `skipped`, or `failed` only, and edits values, never status — re-running a filled-in row is the existing rerun endpoint. `fill` sets one Variable on every `queued` row that has no value for it: the one write behind the "fill the queued rows" banner.

## Acceptance criteria

- [ ] `POST` with 3 rows, one missing a value for a declared non-secret Variable → 201; that row's status is `skipped`, the others `queued`. The same POST with `run_incomplete_rows: true` → all three `queued`.
- [ ] `POST` with 1 001 rows → 413 `too_many_rows` with `max: 1000`.
- [ ] `POST` naming a Variable the latest published Version does not declare → 400 `unknown_variable` naming it; for a Workflow with no published Version → 409 `no_published_version`.
- [ ] `PATCH` a `skipped` row's variables → 200 with status unchanged; the existing rerun then attaches a new Run to that row. `PATCH` a `succeeded`, `running`, or `cancelled` row → 409 `row_not_editable`.
- [ ] `POST /rows/fill` on a Batch with 5 `queued` rows, 3 of which lack `region`, while one further row is `running` → `updated_count: 3`, and the running row is untouched.
- [ ] `GET /api/batches?workflow_id=` returns BatchSummary rows with stats derived from rows; keyset paging over seeded Batches yields distinct ids in order.
- [ ] Every route is user-scoped: another user's Batch id → 404.
