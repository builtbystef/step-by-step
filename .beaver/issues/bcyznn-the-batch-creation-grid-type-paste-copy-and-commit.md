---
id: bcyznn
title: 'The Batch creation grid: type, paste, copy, and commit'
state: todo
priority: medium
depends_on:
    - vguxj7
    - jdgmdx
    - 0746dg
parent: nno9gj
created: 2026-08-14T19:51:44Z
updated: 2026-08-14T19:51:44Z
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
