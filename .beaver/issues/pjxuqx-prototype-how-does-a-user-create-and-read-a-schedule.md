---
id: pjxuqx
title: 'Prototype: how does a user create and read a Schedule?'
state: done
assignee: claude
priority: medium
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - kvz5sv
parent: idnzwf
created: 2026-08-12T01:03:52Z
updated: 2026-08-12T02:15:24Z
---

Live prototype session (prototype skill). The scheduling *engine* is settled — spec 9gea5p fixes cron plus an IANA timezone, overlap means the occurrence is skipped, missed occurrences are never caught up, and a Schedule executes the Workflow's latest published Version. What no node has answered is the surface. Answer with disposable UI:

- How is a recurrence entered by someone who does not know cron: presets, a builder, a raw expression, or a combination — and how is the result read back in words?
- What does the next-run preview show (the next few occurrences, in which timezone, against what "now")?
- How is the timezone chosen, and what does a user see when theirs differs from the instance's?
- How does a Schedule read at rest: last fired, next due, enabled/disabled, and the runs it produced?
- How does the skip-on-overlap rule surface after it fires, so that a missing run is never a mystery?
- Where do Variable values for a scheduled Run come from, given that nobody is present to type them?

The last question may not be answerable as UI alone — if it turns out to be a decision rather than a design, say so in the note and let it become a grill node.

Inputs: the scheduler half of spec 9gea5p, ds8zyn's Variable model, docs/GLOSSARY.md. The result feeds the spec for this area.

## Notes

**claude** — 2026-08-12T02:15:24Z

VERDICT (user's words: "Yes agreed, go with your recommendations") — branch `prototype/schedule-creation`, file `PROTOTYPE-schedule-creation.html` (three creation variants A presets / B sentence / C cron, two at-rest variants 1 workflow panel / 2 all-schedules table, a movable clock, and overlap-skip / instance-down / viewer-timezone / paused scenarios).

RECURRENCE ENTRY — variant B's frame with variant C's preset chips above it. A sentence of dropdowns ("Run {Workflow} [every weekday] at [09:00] in [Europe/Belgrade]") with a row of one-click chips (hourly, every 15 min, daily 09:00, weekdays 09:00, Mondays 07:30, 1st of month) that fill the sentence rather than opening a separate mode. The generated cron is always visible beneath it, and "write cron instead" swaps the sentence for a raw field. Rejected: preset tiles alone (variant A) — they cover the common cases and then drop the user onto a bare cron field at the first intermediate case such as "every 4 hours on weekdays", a cliff in the middle of the range; and cron as the primary control (variant C) — it demands knowledge the product's premise says the user does not have.

READBACK — every surface reads the recurrence back two ways: one sentence in words, and the real next occurrences. The humanizer must DECLINE rather than guess: expressions it cannot phrase shortly (e.g. `*/7 3-5 * * *`) say so and let the occurrence list be the answer. Next 5 occurrences, in the Schedule's own timezone, with the viewer's local time trailing in grey when they differ. Occurrences at rest derive from the row's `next_due_at` so the UI can never disagree with the scheduler.

TIMEZONE — the picker defaults to the browser's IANA zone when it is one the instance knows, else the instance default, and the choice is always stored explicitly. A Schedule is read in its own timezone; the viewer's local time is secondary, in grey, never a replacement. DST is real and was verified: 09:00 Europe/Belgrade correctly moves 07:00Z → 08:00Z across the October change.

VARIABLE VALUES FOR AN UNATTENDED RUN — the value set is owned by the Schedule (variant B), entered in the same grid as Batch creation, one row. This unifies with tf6796: **a Batch is many rows and no clock; a Schedule is one row and a clock** — same grid, same secret column locked to "from vault", same payload shape carrying non-secret values only. `schedules` gains a `variables` JSONB column. Rejected: defaults declared on the Workflow's Variables (variant A) — two Schedules of one Workflow could never differ, and a `default` on the Variable would silently reach manual Runs and Batch rows too. Variant C proved not to be a third answer at all: it is B's storage with a prefill, so it was folded in — but as an explicit "fill from my last Run" BUTTON, never silent prefill, because silent prefill enshrines yesterday's throwaway values (or a test Run's) in a job that then fires unattended forever.

A Schedule with a missing Variable value CANNOT be saved. This is deliberately the opposite of tf6796's ruling for Batch rows, where an incomplete row becomes a `skipped` row: an incomplete batch row is visible in a batch someone is watching, while an incomplete Schedule detonates unattended, on repeat.

AT REST — one table of every Schedule across every Workflow, rows expanding in place (variant 2), is the primary surface; the Workflow's Schedules tab is the SAME component, filtered, not a second one. Reason: the question brought to this screen is instance-wide ("is anything unattended broken or not firing?"), and the per-Workflow panel (variant 1) forces a visit to each Workflow to answer it — the same reasoning apx4rs used to reject master-detail for batch progress. Columns: enabled toggle, Workflow, recurrence in words (with the cron and timezone beneath), next due, last run outcome, and a note column that carries the most recent non-firing occurrence. The expanded row holds the skip banner, the occurrence strip, next occurrences, recent occurrences, and the value set.

A MISSING RUN IS NEVER A MYSTERY — three devices, all confirmed: (1) an occurrence strip that puts past outcomes and future dues on one line, so a hole is visible rather than inferred, with skipped and missed drawn as distinct hatches; (2) a persistent banner naming the occurrence, the reason, and the blocking Run, offering "open the Run that blocked it" and "run it now instead"; (3) the occurrence list interleaving non-firing occurrences with Runs, so the history reads continuously. Skip and miss are told as two DIFFERENT stories: "the previous Run was still running" and "the instance was not running; missed occurrences are never run late".

GAP HANDED TO THE SPEC (3r9p7w) — spec 9gea5p gives `schedules` a single `last_skip_reason` slot, but the surface needs to distinguish overlap from instance-down, and the occurrence strip wants holes older than the most recent one. Minimum fix: an enum plus `last_skip_at`. Fuller fix: persist non-firing occurrences as rows so occurrence history is uniform with Runs. Left for the spec session to settle, not decided here.

The node's fallback ("this may be a decision, not a design → make it a grill node") did NOT trigger: the Variable-values question resolved as design, in the prototype, with the user's agreement.

FEEDS — 3r9p7w, the spec for Batch and Schedule creation.
