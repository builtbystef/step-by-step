---
id: jilt40
title: 'Schedule creation: the sentence builder and the one-row value set'
state: todo
priority: medium
depends_on:
    - k97lxb
    - e2q15g
    - bcyznn
parent: nno9gj
created: 2026-08-14T19:52:25Z
updated: 2026-08-14T19:52:25Z
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
