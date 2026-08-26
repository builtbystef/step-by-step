---
id: jilt40
title: 'Schedule creation: the sentence builder and the one-row value set'
state: done
assignee: agent
priority: medium
depends_on:
    - k97lxb
    - e2q15g
    - bcyznn
parent: nno9gj
created: 2026-08-14T19:52:25Z
updated: 2026-08-26T19:54:05Z
---

## What to build

A recurrence entered by someone who does not write cron, read back convincingly enough to trust an unattended job. The creation and edit surface: preset chips (hourly, every 15 min, daily 09:00, weekdays 09:00, Mondays 07:30, 1st of month) above a sentence of dropdowns — "Run {Workflow} [every weekday] at [09:00] in [Europe/Belgrade]" — with the generated cron always visible beneath, and "write cron instead" swapping the sentence for a raw field. Opening an existing Schedule whose cron is outside the closed grammar lands in raw-cron mode directly. Beneath: the readback in words or the decline (the raw expression shown, the real Occurrences the answer), and the next 5 Occurrences fetched from the preview endpoint, shown in the Schedule's timezone with the viewer's local time trailing in grey when they differ. The words are the client's; the times are never the client's.

The timezone picker defaults to the browser's IANA zone when the instance knows it, else the instance default (one env var, defaulting to UTC); the choice is always stored explicitly. The zone list is the browser's own against the server's.

The value set is the shared grid with exactly one row and the same locked secret column. "Fill from my last Run" is an explicit button that copies the most recent non-test Run's values — there is no silent prefill — and its ground is a backend addition this slice owns: **RunSummary gains `variables`** (non-secret values only). Saving with a non-secret Variable empty is refused.

## Acceptance criteria

- [ ] The "weekdays 09:00" chip fills the sentence, shows `0 9 * * 1-5` beneath, reads back "every weekday at 09:00", and lists 5 next Occurrences fetched from the preview endpoint — asserted on the request, no client-side time computation.
- [ ] Editing the sentence regenerates the cron; "write cron instead" accepts `*/7 3-5 * * *`, the readback shows the decline with the raw expression, and the preview still lists the real times.
- [ ] Opening an existing Schedule whose cron the grammar cannot hold lands in raw-cron mode with the expression intact.
- [ ] The timezone defaults per the rule, is stored explicitly on save, and the viewer's differing local time trails in grey next to each previewed Occurrence.
- [ ] The value set renders as the shared grid with one row and the locked "from vault" secret cell; "Fill from my last Run" copies the most recent non-test Run's values only when clicked.
- [ ] `GET /api/runs` items carry `variables` with non-secret values only: a Run of a Workflow with one plain and one secret Variable lists only the plain one (seam-1 test).
- [ ] Saving with a non-secret Variable empty is refused, naming the Variable; nothing is saved.
- [ ] Saving sends cron, timezone, enabled, variables, and the optional name to the create or edit endpoint.

## Notes

**agent** — 2026-08-26T19:16:53Z

Seam (AFK): the spec names seam 1 for the RunSummary.variables addition (HTTP against the FastAPI app) and seam 2 only for the already-built recurrence module. The sentence builder, timezone default, fill-from-last-Run, empty-value refusal, preview request, and save payload have no named seam. Took the project's established frontend seam — pure functions without a DOM — same as the Batch creation grid. The page draws those functions; it does not re-decide them. Preview times are asserted on the request body, never computed here.

Timezone: DEFAULT_TIMEZONE (unset = UTC) is exposed as default_timezone on GET /api/instance, which is how the picker applies "browser zone when the instance knows it, else the instance default". The zone list is Intl.supportedValuesOf('timeZone'); the server still refuses an unknown zone on save.

**agent** — 2026-08-26T19:54:05Z

Completed Schedule creation: the sentence builder and the one-row value set.

Seams
- Seam 1 (named): GET /api/runs items carry variables (non-secret only). HTTP against the FastAPI app.
- Frontend: pure functions without a DOM (creation.ts), same as the Batch grid. The page draws them.

What landed
- /workflows/{id}/schedules/new and /workflows/{id}/schedules/{scheduleId}. New schedule in the list overflow and the Workflow header overflow goes there. The Schedules tab stays current.
- Preset chips (hourly, every 15 min, daily 09:00, weekdays 09:00, Mondays 07:30, 1st of month) above the sentence of dropdowns, generated cron always visible, "write cron instead" swaps in a raw field. Opening a cron the grammar cannot hold lands in raw mode with the expression intact.
- Readback via humanize (or the raw expression when it declines). Next 5 Occurrences from POST /api/schedules/preview — asserted on the request body, never computed here. Viewer-local time trails in text-mut when it differs from the Schedule's zone.
- Value set is ValueGrid with fixedRowCount={1}. "Fill from my last Run" copies the newest non-test Run's variables only when clicked. Empty non-secret Variables refuse save, naming them; mutate is not called.
- Save sends cron, timezone, enabled, variables, and optional name to create or patch.
- RunSummary.variables on GET /api/runs. DEFAULT_TIMEZONE (unset = UTC) on GET /api/instance as default_timezone, proven at boot.

Decisions
- 1st of month chip is 00:00 on day 1 (`0 0 1 * *`); the spec named no time.
- Zone list is Intl.supportedValuesOf('timeZone'); the server still 400s an unknown zone on save.
- After save, navigate to /workflows/{id}/schedules (the tab; the table is l88wkp).
- New Schedule defaults to daily 09:00 until a chip or the sentence says otherwise.

For a reviewer
- Seam-1: test_run_summaries_carry_non_secret_variables.
- Chip / raw cron / open-existing / timezone default / trailing local / fill-from / empty refusal / save payload: creation.test.ts.
