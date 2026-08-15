---
id: vl4dsk
title: 'The Workflow changed: the two new-Variable banners'
state: todo
priority: medium
depends_on:
    - bcyznn
    - 91gsby
parent: nno9gj
created: 2026-08-14T19:52:25Z
updated: 2026-08-14T19:52:25Z
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
