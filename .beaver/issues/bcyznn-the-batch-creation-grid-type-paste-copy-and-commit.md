---
id: bcyznn
title: 'The Batch creation grid: type, paste, copy, and commit'
state: done
assignee: agent
priority: medium
depends_on:
    - vguxj7
    - jdgmdx
    - 0746dg
parent: nno9gj
created: 2026-08-14T19:51:44Z
updated: 2026-08-26T19:08:46Z
---

## What to build

One page, always a grid. The columns are the Workflow's declared Variables in declaration order; the destination table exists before any file does, so typing rows, pasting a table, and copying a past Batch's rows are one surface rather than separate flows (file import lands in its own slice, into this same grid). A secret Variable is a permanently visible **locked column**, headed with the Variable's name and reading "from vault" with the bound Secret's cached name — never editable, never sent, so the rule that a secret never travels in a row is a standing property of the screen.

The sticky footer carries: the Batch name, defaulting to `{Workflow name} — {date}` or `… — rerun of {Batch}` when copied; the total / complete / missing-a-value counts; the incomplete-row policy with its "run them anyway" checkbox (the `run_incomplete_rows` flag); and the sequential ETA — the Workflow's recent-run median × the row count when the median exists, otherwise a line like `12 Runs, one at a time` with no time rather than a guess. Submitting creates the Batch and navigates to its progress view.

The grid is **one shared component**: the Schedule's one-row value set and the run-start value grid are this same component, not second implementations.

## Acceptance criteria

- [ ] The grid's columns follow declaration order; the secret column is locked, reads "from vault" with the Secret's cached name, and cannot be edited; the submitted payload carries nothing for the secret Variable (asserted on the request body).
- [ ] Typing rows works cell by cell; pasting a multi-row, multi-column table copied from a spreadsheet lands as correctly split rows and cells.
- [ ] "Copy from a past Batch" lists the Workflow's Batches from the batches list endpoint; picking one lands its rows in the grid and names the new Batch `… — rerun of {name}`.
- [ ] Footer counts: 5 rows of which 2 miss a value → total 5, complete 3, missing 2; the checkbox unchecked submits `run_incomplete_rows: false`, checked submits `true`.
- [ ] With a recent-run median of 90 s and 12 rows, the footer shows an 18-minute ETA; with fewer than 3 succeeded Runs it shows `12 Runs, one at a time` and no time.
- [ ] Submit → 201 → the app navigates to the Batch's progress view.
- [ ] No second grid implementation exists: the component is exported for the one-row consumers, and rendering it with one fixed row shows the same locked secret cell.

## Notes

**agent** — 2026-08-26T19:08:39Z

Completed. Seam (AFK): the spec's Testing Decisions name seam 2 for reconcile and recurrence, not this grid. Took the project's established frontend seam — pure functions without a DOM — and recorded it here. grid.ts is columns, the locked cell label, paste, copy-from mapping, and a payload that never carries a secret; creation.ts is the default name, the rerun name, footer counts' submit flag, the sequential ETA, and the progress-view href. The page draws these; it does not re-decide them. The request body is asserted on createBody.

What landed
- Shared ValueGrid at apps/web/components/value-grid, exported for one-row consumers (fixedRowCount={1}). Secret columns are locked, headed with the Variable's name, and read "from vault" plus the cached Secret name; setCell and the submitted payload omit them.
- /workflows/{id}/batches/new: type cell by cell, paste a spreadsheet TSV into split rows and cells, copy from a past Batch (listBatches then getBatch for rows), sticky footer with name / counts / "Run them anyway" / ETA, submit createBatch and navigate to /batches/{id}.
- New batch in the list overflow and the Workflow header overflow goes to that page. The Batches tab stays current on it.

Decisions
- Default name is `{Workflow} — 26 Aug 2026` from local calendar parts. Copied rows rename to `{Workflow} — rerun of {Batch}`.
- ETA with a median is `about 18 min` (duration of median × rows). Below 3 succeeded Runs the summary has no median, so the line is `12 Runs, one at a time` with no time.
- Paste overlays from the focused cell, TSV, locked columns refuse the write but still occupy a column. File import is 560jkk.
- Copy-from lists via GET /api/batches?workflow_id=; summaries do not carry rows, so picking one GETs the Batch.
- Run again remains a labeled form, not a second grid. immifu and jilt40 consume ValueGrid.

For a reviewer
- Payload secret-omission and run_incomplete_rows true/false are asserted on createBody.
- Footer 5/3/2, 90s×12 → about 18 min, and one-row locked cell are in grid.test.ts / creation.test.ts.
