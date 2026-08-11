---
id: apx4rs
title: 'Prototype: what must the live run view and timeline look like?'
state: done
assignee: claude
priority: medium
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - px25yw
    - 4tjwpw
parent: idnzwf
created: 2026-08-10T03:34:26Z
updated: 2026-08-11T23:40:52Z
---

Live prototype session (prototype skill). The execution architecture is settled (px25yw): run states queued/running/waiting_for_human/succeeded/failed/cancelled with machine-readable failure reasons; step status, log lines, and screenshot-ready events arrive over SSE; screenshots are fetched as Artifacts by URL; a Batch's Runs execute sequentially. Answer with disposable UI:

- How does a single Run read while it executes: step progress, current step, logs, screenshots — and after it ends?
- How does the timeline render state transitions, including waiting_for_human intervals (entering/leaving takeover is 4tjwpw's ground — this view only shows that it happened)?
- What does a Batch's progress view look like: row-by-row status, the current Run, failed rows among succeeded ones?
- Where does drift visibility surface (a step that resolved on a low-ranked selector, wljln8) in the run detail?
- What does cancellation look like from this view?

Inputs: px25yw's note, ds8zyn's note (Step Result), docs/GLOSSARY.md. Coordinate with 4tjwpw (takeover UX) — this view hands off to it. The result feeds the backend + workers + live run spec.

## Notes

**claude** — 2026-08-11T23:40:52Z

## Question

What must the live run view and its timeline look like? Answered with a disposable UI prototype (branch `prototype/live-run-view`, file `PROTOTYPE-live-run-view.html` — one self-contained HTML page, opens directly in a browser; a harness bar plays a scripted run at 1/4/16x with jump points, two scenarios, and a working cancel). Verdict is the user's: "I like A, and the table for batch runs. Go with your recommendation."

## Verdict

**Run detail: layout A — cockpit.** Steps in a left rail, the embedded browser pane (4tjwpw's) as the main pane, a Logs / Output / Artifacts drawer beneath it, and the timeline as a compact strip under the header. It gives the pane the most room, which is what a live run is watched for. Rejected as the primary layout: B timeline-spine (pushes the pane into a sidebar) and C ops-console (see Out of scope).

**The header carries the run's shape at a glance:** workflow name, run id, Version, trigger, a status chip (queued / running / waiting for human / succeeded / failed / cancelled), and a meta row of elapsed · automation time · time with you · steps done · worker · timeout, plus `failure_reason` once terminal. A `⚠ N steps drifted` chip appears beside the status when any step resolved on a low-ranked candidate.

**Timeline = a proportional strip of control intervals**, not a step chart: automation (blue), waiting for you (amber striped), you in control (purple), verifying (teal), with event markers beneath (paused · you took control · handed back · resumed) and a legend. Run status stays `waiting_for_human` across the waiting/human/verifying sub-phases — the strip shows who had control, the chip shows the run state.

**Control phases also appear inline in the step rail** (grafted from B at the user's confirmation): between the pause-for-takeover step and the next step sit three compact bands — "waiting for you — 0:06", "you were in control — 0:11 · 00:15→00:26", "verifying the success check — 0:02 · passed, automation resumed". The rail then reads as the full sequence of what happened, human interval included, without spending the pane's width.

**A step row** shows number, editable label, the narrative sentence (matching the editor, 3iwv5i), duration, and badges: drift, "completed by you · verified ✓", selector failure, skipped, "24 records", "1 file". Clicking a step expands its detail in place: error banner, drift panel, its screenshots, its extracted data, and its own log lines filtered from the stream.

**Selector Drift surfaces in three places** (wljln8's run-detail half): a `found on candidate 3/5` badge on the step row; the `⚠ N steps drifted` chip in the header; and, in the expanded step, a ranked candidate list showing which candidates died, which matched, and a link to re-pick the element in the editor. Repair stays in the editor — the run view only reports.

**After the run ends** the same view persists: the pane holds the final page ("session ended — the browser closed"), a terminal banner states the outcome in words (succeeded in 0:39 · 8 of 8 steps · 24 records · 1 download / failed at step 6 · `step_failed` · remaining 2 steps skipped, with a "Re-pick the element" action), the Output tab shows the Run's assembled output object as a table with Download JSON / CSV, and Artifacts lists screenshots, the trace (Open in Trace Viewer), and downloads.

**Cancellation** is a header button → an inline confirm that states the rule in plain language: the worker finishes the action it is on and stops at the next step boundary, never mid-click; completed steps keep their results, the rest are marked skipped. While running, a dashed "Cancelling… waiting for step N to reach a boundary" banner covers the gap. While `waiting_for_human` there is no action in flight, so cancelling ends the takeover and closes the browser at once (px25yw).

**Batch progress: the table.** Rows as a table — number, the row's variable values, status chip, duration, and a live badge on the running row — with a stats header (rows done, succeeded, failed, queued, skipped) and a segmented progress bar with an ETA. Any row expands in place: the live row into a mini run view (control-interval strip, step list, log tail, "Open the full run"), a failed row into its failure reason plus "Open the run" and "Re-run just this row", a succeeded row into its output. Failed rows sit among succeeded ones with their reason on the row, since a failed row never strands the rest (wljln8). Rejected: master-detail, which forces a selection and spends half the screen on a row nobody asked about.

**A batch that stalls on a human is stated as such.** When the current row enters `waiting_for_human`, an amber callout sits above the table: "Row 12 (Woodgrove Bank) is waiting for you — runs in a batch go one at a time, the other 8 rows stay queued until this one is dealt with", with the takeover countdown, what a timeout does (this row fails, the batch moves on), and "Take over row 12" / "Skip this row". **Cancelling a batch** cancels the current Run and marks the remaining rows skipped (px25yw), stated in the header.

**A Batch's Output tab** is the uniform table across rows (row, its variables, its extracted values, a link to its Run) with Download all as CSV / JSON; rows that failed have no output.

## Reason

A is the arrangement that serves the view's primary job — "does this run need me right now?" — because that answer lives in the browser pane, and A gives the pane the most room while keeping the step rail readable. It also inherits 4tjwpw's settled pane placement unchanged, so takeover and watching share one surface. B's per-step expansion and its inline control phases were the two things it did better, and both graft into A without cost, which is what the final prototype shows. The table beats master-detail for batches because a batch's work is scanning many rows for the few that need attention, and the variable values that distinguish rows are columns.

Prototype code: branch `prototype/live-run-view`, single file `PROTOTYPE-live-run-view.html`. Feeds spec node kvz5sv (execution, workers, and the live run view), together with px25yw, 1ar6xu, 4tjwpw, and wljln8.
