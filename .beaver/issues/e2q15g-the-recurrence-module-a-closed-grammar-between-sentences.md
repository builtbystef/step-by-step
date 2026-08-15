---
id: e2q15g
title: 'The recurrence module: a closed grammar between sentences and cron'
state: todo
priority: medium
parent: nno9gj
created: 2026-08-14T19:51:01Z
updated: 2026-08-14T19:51:01Z
---

## What to build

A pure frontend module that is the only bridge between the sentence builder's dropdowns and a cron expression. The grammar is closed: it expresses exactly what the sentence can say, and it declines everything else rather than guessing. The words are the client's; the times are never the client's — Occurrence times always come from the preview endpoint.

```
type Recurrence =
  | { kind: "everyNMinutes", n: number }
  | { kind: "hourly", minute: number }
  | { kind: "daily", hour: number, minute: number }
  | { kind: "weekdays", hour: number, minute: number }
  | { kind: "weekly", weekdays: number[], hour: number, minute: number }
  | { kind: "monthly", day: number, hour: number, minute: number }

toCron(r: Recurrence): string
fromCron(cron: string): Recurrence | null    // null: outside the grammar
humanize(cron: string): string | null        // null: declines to phrase it
```

## Acceptance criteria

- [ ] `toCron` maps each shape to its cron: weekdays at 09:00 → `0 9 * * 1-5`; every 15 minutes → `*/15 * * * *`; monthly day 1 at 07:30 → `30 7 1 * *`.
- [ ] `fromCron(toCron(r))` equals `r` for a representative value of every `Recurrence` kind — the round-trip is the module's core property.
- [ ] `fromCron("*/7 3-5 * * *")` → `null`: an expression outside the grammar is declined, never approximated.
- [ ] `humanize("0 9 * * 1-5")` → `"every weekday at 09:00"`; `humanize("*/7 3-5 * * *")` → `null` — the readback is never a lie.
- [ ] The tests call the module as functions with no DOM and no component rendering (seam 2).
