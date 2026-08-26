---
id: l88wkp
title: 'The Schedules table: the strip, the holes, and their stories'
state: done
assignee: agent
priority: medium
depends_on:
    - k97lxb
    - jilt40
parent: nno9gj
created: 2026-08-14T19:52:41Z
updated: 2026-08-26T20:41:56Z
---

## What to build

The at-rest surface's content: the Schedule row and its expansion. (The one-component/two-route wiring — global route plus the Workflow's Schedules tab — is the shell spec's slice; this slice builds the table content it mounts.) Columns: the enabled toggle, the Workflow, the recurrence in words with the cron and timezone beneath (the raw expression when the grammar declines), next due, the last Run's outcome, and a note column carrying the most recent non-firing Occurrence.

A row expands in place to: the skip banner, the Occurrence strip, the next Occurrences, the recent history, and the value set. Three devices keep a missing Run from being a mystery: (1) the strip puts past outcomes and future dues on one line, with `overlap`, `missed`, and `missing_values` drawn as three distinct hatches; (2) a persistent banner names the Occurrence, its reason, and the blocking Run, offering "open the Run that blocked it" and "run it now instead"; (3) the history list interleaves Occurrences with Runs so it reads continuously. Overlap and missed are two different stories — "the previous Run was still running" and "the instance was not running; missed Occurrences are never run late" — and `missing_values` a third, naming the Variable. A `needs_values` Schedule shows a red banner naming the Variables and a control to set them (opening the edit surface's value set); it is visibly distinct from `paused`, and a paused interval shows a paused band, never a run of holes.

## Acceptance criteria

- [ ] A row shows the recurrence in words with cron and timezone beneath; a Schedule whose cron the grammar cannot phrase shows the raw expression instead; the note column carries the latest non-firing Occurrence and is empty for a healthy Schedule.
- [ ] The expanded strip renders Runs and the three hole kinds as four visually distinct marks, past outcomes and future dues on one line; the history of a Schedule with two Runs and one `overlap` row reads as three entries in time order, of both kinds.
- [ ] The overlap banner names the blocking Run and its reason; "open the Run that blocked it" navigates to that Run; "run it now instead" calls run-now, and a `schedule_run_active` refusal is surfaced in place, not swallowed.
- [ ] The three reasons carry their three distinct stories: previous-Run-still-running, instance-not-running-and-never-run-late, and this-Workflow-now-needs-`region`.
- [ ] A `needs_values` Schedule shows the red banner naming the missing Variables, whose control opens the value set for editing; it looks unmistakably different from a `paused` one.
- [ ] The enabled toggle patches `enabled`; a paused Schedule's expansion shows a paused band for the interval, with no holes accrued.
- [ ] Next Occurrences appear in the Schedule's timezone with the viewer's differing local time in grey.

## Notes

**agent** — 2026-08-26T20:02:31Z

Seam (AFK): the spec names seam 1 (HTTP) and seam 2 (reconcile + recurrence module) only. The table, strip, banners, and stories have no named seam. Took the project's established frontend seam — pure functions without a DOM — same as Schedule creation and the Batch grid. The page draws those functions; it does not re-decide them.

Occurrence times in the expansion come from GET /api/schedules/{id} (next_occurrences, history); this module only phrases timestamps it is given. Recurrence words come from humanize (seam 2 already built).

HatchedOccurrence: 8cjj8g left where missed falls to this strip. The three hole kinds are three hatch kinds (overlap = prevented/amber, missed = grey at a distinct angle, missing_values = bad/red) so Runs plus the three holes are four visually distinct marks. The paused interval is a never-due band, not holes.

**agent** — 2026-08-26T20:41:56Z

Completed the Schedules table content: the row and its in-place expansion.

Seam: pure functions without a DOM (presentation.ts). The page draws them.

What landed
- /schedules renders the table. The Workflow tab stays a placeholder — one-component/two-route wiring is yf7vq2.
- Row: enabled toggle (PATCH enabled), Workflow, recurrence in words (humanize) with cron and timezone beneath (raw expression when the grammar declines), next due, last Run as StatusChip, note column with the latest hole story (empty when healthy).
- Expansion: skip banner, Occurrence strip (past outcomes and future dues on one line), next Occurrences, interleaved history, value set.
- Four strip marks: Run (StatusChip), overlap (amber 45° hatch), missed (grey 135° hatch), missing_values (red 45° hatch). Paused interval is a never-due band, no holes synthesized.
- Overlap banner names the blocking Run and the still-running story; "Open the Run that blocked it" goes to /runs/{id}; "Run it now instead" calls run-now; schedule_run_active is shown in place.
- Three stories: previous Run still running; instance not running / never run late; this Workflow now needs `region`.
- needs_values is a red Callout naming the Variables with Set values → the edit surface; paused has no red banner and a paused band.

Decisions
- HatchedOccurrence gained missed and missing-values kinds. 8cjj8g left missed to this strip; three hole kinds are three hatches so the four marks are distinct. missing_values uses --bad because the needs_values banner is red.
- Next-Occurrence labels reuse occurrenceLabel from the creation module (same phrasing, grey local in text-mut).
- Detail is fetched only once a row is expanded.

For a reviewer
- presentation.test.ts covers every acceptance criterion.
- Visual language scan still holds (no raw hex, no lifecycleLabel outside StatusChip).
