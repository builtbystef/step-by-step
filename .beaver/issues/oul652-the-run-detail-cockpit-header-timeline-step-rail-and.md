---
id: oul652
title: 'The run detail cockpit: header, timeline, step rail, and terminal states'
state: todo
priority: medium
depends_on:
    - 1q7qp8
    - it3m03
    - qmnvgr
    - 5rkj33
    - tls69i
parent: 9gea5p
created: 2026-08-14T07:44:24Z
updated: 2026-08-17T04:03:58Z
---

## What to build

The screen where a Run is understood, settled by the prototypes and restated as requirements. The layout: a left rail of Steps, the main pane area (the embedded browser arrives with the pane slice — until then the area holds its states' placeholders), a Logs / Artifacts drawer beneath, and a compact timeline strip under the header.

- **Header**: workflow name, run id, Version, trigger, status chip, and a meta row — elapsed · automation time · time with you · steps done · worker · timeout — plus `failure_reason` once terminal. A `⚠ N steps drifted` chip appears when any Step resolved on a low-ranked candidate.
- **Timeline strip**: proportional control intervals — automation, waiting (amber striped), you in control (purple), verifying (teal) — with event markers beneath and a legend, rendered from `run_control_intervals` directly.
- **Step rail**: number, label, the narrative sentence matching the editor, duration, and badges — drift (`found on candidate 3/5`), "completed by you · verified ✓", selector failure, skipped, record and file counts. A Step expands in place into its error, its drift panel (the ranked candidates — which died, which matched — and a link to Re-pick in the editor), its screenshots, its extracted data, and its own log lines. Control phases appear inline between Steps as compact bands with durations.
- **Live**: the screen follows SSE events as the Run progresses; reconnect refetches over REST.
- **Terminal**: a banner states the outcome in words — `succeeded in 0:39 · 8 of 8 steps · 24 records · 1 download`, or `failed at step 6 · step_failed · remaining 2 steps skipped` with a "re-pick the element" action.
- **Cancel**: an inline confirm stating the boundary rule in plain language, then the "cancelling — waiting for step N to reach a boundary" band until the terminal event.
- **Run again**: opens the run dialog prefilled with this Run's Variable values, executing the latest published Version.

## Acceptance criteria

- [ ] A live Run's rail ticks through its Steps as `step.started`/`step.finished` arrive, with durations and badges appearing without a reload.
- [ ] A Run with a rank-3 match on one Step shows the header drift chip `⚠ 1 step drifted` and the Step's `found on candidate 3/5` badge; its expansion shows the ranked candidates and links to Re-pick in the editor.
- [ ] The timeline of a Run that waited and was taken over renders four interval kinds proportionally with markers, straight from the intervals in the detail response.
- [ ] A failed Step's expansion shows its error, its always-taken failure screenshot, and only its own log lines.
- [ ] The terminal banner for a seeded successful Run reads exactly in the pattern `succeeded in 0:39 · 8 of 8 steps · 24 records · 1 download`; a failed Run's names the failing step, the reason, and the skipped count.
- [ ] Cancel shows the plain-language confirm, then the cancelling band, and resolves to the terminal banner when the event arrives.
- [ ] Run again opens the dialog prefilled with the Run's Variable values.
- [ ] The status chip is the only element rendering lifecycle state, in the app's semantic hues.

## Notes

**claude** — 2026-08-17T04:03:58Z

Added blocking edge on tls69i: the cockpit's ACs render failure screenshots and per-step artifact expansions that tls69i lands.
