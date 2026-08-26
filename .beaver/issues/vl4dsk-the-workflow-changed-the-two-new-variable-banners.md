---
id: vl4dsk
title: 'The Workflow changed: the two new-Variable banners'
state: done
assignee: agent
priority: medium
depends_on:
    - bcyznn
    - 91gsby
parent: nno9gj
created: 2026-08-14T19:52:25Z
updated: 2026-08-26T22:26:01Z
---

## What to build

A Workflow that gains a Variable must not quietly reach unattended Runs. Two banners, one story:

**While building a Batch**: the page compares the Version it loaded against the latest published Version on window refocus and again before submit, and shows a banner offering "give every row the same value" for the new Variable. No Version token is sent — a Batch always executes the latest published Version at run time.

**While a Batch is running** (on the batch progress view): when the latest Version declares a Variable, a banner names how many `queued` rows have no value for it and offers fill-the-queued-rows (one write, the rows/fill endpoint), run-them-as-they-are, or cancel-the-rest. Succeeded and running rows are untouched.

## Acceptance criteria

- [ ] Build a Batch, publish a Version adding `region` in another tab, refocus the page → the banner names `region`; "give every row the same value" takes one entered value and fills the new column on every row.
- [ ] With no refocus, the pre-submit check still catches the drift: the banner appears before the POST is sent.
- [ ] A running Batch with 3 `queued` rows lacking `region` → the banner reads that 3 queued rows have no value for it; choosing fill issues exactly one rows/fill call and the banner clears with the rows updated.
- [ ] Run-them-as-they-are dismisses the banner with no write; cancel-the-rest cancels the Batch through the existing cancel action.
- [ ] Succeeded and running rows are visibly untouched by the fill.

## Notes

**agent** — 2026-08-26T22:25:58Z

Seam (AFK): the spec's Testing Decisions name seam 2 for reconcile and recurrence, not these banners. Took the project's established frontend seam — pure functions without a DOM — and recorded it here. creation.ts is the loaded-vs-latest Variable diff, the banner copy, and the pre-submit block; grid.ts fillEveryRow is the one entered value on every row; presentation.ts is the running banner's queued count, the one rows/fill body, applyQueuedFill leaving succeeded/running untouched, and run-them-as-they-are dismiss. The pages draw these; they do not re-decide them.

What landed
- New-batch page: snapshots the Version it loaded; on window focus and again before createBatch, fetches the latest published Variables. A new non-secret Variable (region) raises a warn banner that names it; "Give every row the same value" fills the new column on every row. The POST is not sent while that drift is unfilled. No Version token is sent.
- Batch progress view: when the latest Version declares a Variable that queued rows lack, a banner reads "N queued rows have no value for {name}". Fill issues exactly one fillBatchRows call; the banner clears with those rows updated. Run them as they are dismisses with no write. Cancel the rest calls cancelBatch.

Decisions
- Secret Variables are not new-column drift — they stay on the Version binding.
- Fill requires a non-empty value. Multiple new Variables are offered one at a time in declaration order.
- Creation blocks submit until the new Variable has been filled through the banner (or is no longer new against the baseline). Incomplete-row policy then applies as before.
- Running-banner dismiss is session-local for that Variable name; a later Variable still raises its own banner.

For a reviewer
- Payload fill is asserted on fillRowsBody / createBody after fillEveryRow.
- 3 queued lacking region, succeeded and running untouched, and dismiss-with-no-write are in presentation.test.ts.
