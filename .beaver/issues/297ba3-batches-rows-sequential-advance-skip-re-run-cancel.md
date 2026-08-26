---
id: 297ba3
title: 'Batches: rows, sequential advance, skip, re-run, cancel'
state: done
assignee: agent
priority: medium
depends_on:
    - 423dg6
    - 6ewr2p
    - 1q7qp8
    - it3m03
parent: 9gea5p
created: 2026-08-14T07:45:08Z
updated: 2026-08-26T12:12:33Z
---

## What to build

Fifty repetitions as one action. The `batches` and `batch_rows` tables: a row carries its index, its Variable values, and a status (queued | running | succeeded | failed | skipped | cancelled) that reflects its latest attempt; a row's Runs point back at it; counts are always derived from rows, never stored twice. Secret values never travel in rows — a secret Variable stays a binding.

Rows execute sequentially — exactly one Run of a Batch is non-terminal at a time. Advance is driven by the terminal-status event the backend already consumes for SSE fan-out, with the periodic loop as backstop for a missed event: no minute-long gap between rows. A failed row never strands the Batch. Skip (offered while a row waits on a human) cancels that row's Run, marks the row `skipped`, and advances at once. Re-run attaches a new attempt to the same row without disturbing the others or reopening a finished Batch. Cancel cancels the current Run and marks every remaining row `cancelled`. ETA is the median duration of completed rows times rows remaining, shown only once at least three rows have finished. Batch events stream on their own SSE channel.

```
POST /api/workflows/{id}/batches  {name, rows: [{variables}]} → 201 {batch_id}
GET  /api/batches/{id}            → 200 {batch, rows, stats, eta_seconds?}
GET  /api/batches/{id}/output?format=json|csv → 200 uniform table
GET  /api/batches/{id}/events     (SSE)   batch.row {batch_id, row_index, status, run_id?, at}
POST /api/batches/{id}/cancel     → 202
POST /api/batches/{id}/rows/{n}/skip  → 202
POST /api/batches/{id}/rows/{n}/rerun → 201 {run_id}
```

The Batch creation UI (upload, column mapping) is out of scope; this endpoint is what a Batch needs to exist and execute.

## Acceptance criteria

- [ ] A Batch of five rows: driving each Run to terminal advances exactly one row at a time, `trigger` = `batch` on each Run, and at no point are two of the Batch's Runs non-terminal.
- [ ] Row advance follows the terminal event immediately — the next Run exists without waiting for a periodic tick; with events silenced, the backstop tick still advances it.
- [ ] Row 2 failing → rows 3–5 still run, and the Batch finishes with the failure visible in its stats.
- [ ] `rerun` on failed row 2 → a new Run attached to row 2, the row's status follows the new attempt, and the earlier attempt is still listed.
- [ ] `skip` on a row waiting for a human → its Run cancelled, the row `skipped`, the next row's Run created at once.
- [ ] Cancel mid-row-3 → row 3's Run cancelled, rows 4–5 `cancelled`, stats derived accordingly.
- [ ] ETA is absent until three rows have finished, then equals median completed-row duration × rows remaining.
- [ ] The Batch output over five rows → one table whose columns are the union of the rows' Variables and output names, in both formats.
- [ ] `batch.row` events stream on the Batch channel as rows change status.

## Notes

**agent** — 2026-08-26T11:01:49Z

Seams from the parent spec: (1) backend HTTP against Postgres and Redis for create/get/output/skip/rerun/cancel, org Membership → 404, sequential one-non-terminal-run, ETA, and the uniform output table; (2) the batch-advance step invoked directly as a function for the terminal-event path, and tick() as the silenced-event backstop; (3) live uvicorn for GET /api/batches/{id}/events, same reason TestClient buffers SSE.

**agent** — 2026-08-26T12:12:33Z

Completed from the timed-out loop iteration's leftover. All nine acceptance criteria have integration tests at the seams recorded earlier (HTTP against Postgres/Redis; on_terminal_run vs tick() for advance; live uvicorn for SSE).

What landed: batches/batch_rows tables and migration; POST create (published Version required, secrets stripped from rows); GET detail with derived stats and eta_seconds (blank until three succeeded/failed rows, then median duration × remaining); JSON/CSV output; skip of a waiting row; rerun of a failed/skipped row while the Batch is idle; cancel of remaining queued rows plus the current Run; sequential one-non-terminal-Run invariant; batch.row SSE; org Membership → 404.

Advance: on_terminal_run from the runs:terminal copy (and from cancel/skip/abandon on a Batch Run); tick() calls advance_stalled_batches as the missed-event backstop. Batch Runs have trigger=batch and no starter.

No new decisions. Reviewer: the Batch creation UI is still out of scope (nno9gj).
