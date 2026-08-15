---
id: fkgat7
title: 'The attention system: endpoint, band, and count badge'
state: todo
priority: medium
depends_on:
    - hat4cf
    - 423dg6
parent: pc0t8s
created: 2026-08-14T05:55:24Z
updated: 2026-08-14T07:45:35Z
---

## What to build

The shell's promise that a waiting Run is visible everywhere. One small polled endpoint reports the caller's non-terminal Runs — the soonest-deadline waiting ones plus three counts — behind a partial index so its cost is independent of Run history. The shell renders it as an amber attention band across the content column (above the page title) and a count badge on the Runs nav item. The countdown is client-side, so the poll never makes the timer coarse, and the client never asserts an outcome it did not observe: the reaper owns the timeout.

## Acceptance criteria

- [ ] The attention endpoint returns, for the active Organization only (the `X-Organization` header): up to 5 waiting entries (run id, workflow id and name, deadline) ordered soonest deadline first; the true waiting count; the running count; the queued count. An Organization with 7 waiting Runs gets exactly 5 entries and a count of 7; one with none gets an empty list and three zeros, with other Organizations' waiting Runs invisible.
- [ ] A partial index over the caller's non-terminal Runs serves the query: with 50 000 terminal Runs and 3 non-terminal ones, the query plan uses it and touches 3 rows — asserted by examining the plan in a test, so the cost claim is a test rather than a hope.
- [ ] The shell polls every 10 seconds only while the tab is visible, refetches on focus, and never polls outside the shell; the query is invalidated (not waited out) by any action that can change it — starting a Run, cancelling one, handing back control — and by a run detail's stream reporting a transition into or out of waiting; the same actions invalidate the Runs list so the two never disagree.
- [ ] The band's wording follows the count: one waiting Run names it ("**Invoice download — AcmeBank** is waiting for you"); several read "**3 Runs** are waiting for you — the soonest is …"; the countdown is the soonest deadline, monospace, ticking client-side; the one action is Take control, navigating to the Run.
- [ ] When a countdown reaches zero the band reads that the deadline has passed, and the next poll clears it — the client never flips a Run's state itself.
- [ ] The Runs nav badge shows running + queued + waiting, hidden at zero, amber when anything waits and blue otherwise, and stays visible on the icon rail.
- [ ] HTTP seam tests with a real Postgres cover the capped list, the ordering, the per-Organization isolation, and the plan assertion.
