---
id: 297ba3
title: 'Batches: rows, sequential advance, skip, re-run, cancel'
state: todo
priority: medium
depends_on:
    - 423dg6
    - 6ewr2p
    - 1q7qp8
    - it3m03
parent: 9gea5p
created: 2026-08-14T07:45:08Z
updated: 2026-08-14T07:45:08Z
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
