---
id: 91gsby
title: 'The batch view: the table, row expansion, and the stalled callout'
state: done
assignee: agent
priority: medium
depends_on:
    - 297ba3
    - oul652
    - qmnvgr
parent: 9gea5p
created: 2026-08-14T07:45:21Z
updated: 2026-08-26T18:30:07Z
---

## What to build

The Batch as a screen. Rows as a table — number, the row's Variable values, status chip, duration, a live badge on the running row — under a stats header (done / succeeded / failed / queued / skipped) and a segmented progress bar with the ETA. The screen follows the Batch's SSE channel.

Any row expands in place: the live row into a mini run view (control strip, Step list, log tail, "open the full run"); a failed row into its reason plus "open the run" and "re-run just this row"; a succeeded row into its output. When the current row enters `waiting_for_human`, an amber callout above the table names the row, states in words that rows run one at a time and the others stay queued, shows the countdown and what a timeout does (this row fails, the Batch moves on), and offers "take over row N" and "skip this row". The Output tab is the uniform table across rows with download-all.

## Acceptance criteria

- [ ] A five-row Batch renders the table with stats, the segmented bar, and the live badge moving row to row as `batch.row` events arrive, without a reload.
- [ ] The ETA area is blank until three rows have finished, then shows the endpoint's estimate.
- [ ] Expanding the live row shows its Steps progressing and a log tail; "open the full run" lands on that Run's cockpit.
- [ ] Expanding a failed row shows its `failure_reason` in words with "open the run" and "re-run just this row"; the re-run action attaches a new attempt and the row's chip follows it.
- [ ] A row entering `waiting_for_human` raises the amber callout naming the row, with the countdown, the stated consequence, and working "take over row N" and "skip this row" actions.
- [ ] Skipping from the callout marks the row skipped and the badge moves to the next row.
- [ ] The Output tab renders the uniform table and downloads both formats.
- [ ] Status chips are the only lifecycle rendering, in the semantic hues.

## Notes

**agent** — 2026-08-26T17:56:51Z

Seams: the parent spec names HTTP and the Worker executor; this slice is the batch view UI. Following the established frontend seam (oul652 / 5rkj33): pure functions for stats/progress/ETA, live-badge movement from batch.row events, row expansion copy, the stalled callout, skip/re-run effects, and Output-tab URLs — read back with no DOM. StatusChip remains the only lifecycle renderer. The live row's mini run reuses the cockpit's event reducer and rail.

**agent** — 2026-08-26T18:30:07Z

Built the Batch screen at /batches/[id].

Seams (unchanged from the earlier note): presentation.ts and events.ts, read back with no DOM. StatusChip is the only lifecycle renderer. The live row's mini run reuses the cockpit's event reducer (applyRunEvent) and railItems.

What landed:
- Stats header (done / succeeded / failed / queued / skipped), segmented bar, live badge that moves on batch.row, ETA blank until the endpoint sends an estimate.
- Expandable rows: live → Steps + log tail + "open the full run"; failed → failure_reason in words + open + re-run; succeeded → that row's output.
- Amber stalled callout on waiting_for_human: names the row, sequential rule, countdown, timeout consequence, take over / skip. Skip and re-run call the batch row endpoints; take over holds the Run then opens the cockpit.
- Output tab: uniform table, Download JSON / CSV.

Checks: vp check clean on the frontend; vp test 399 passing including the 17 new batch-view tests and visual-language. Python unit tests unchanged and passing via the existing venv.
