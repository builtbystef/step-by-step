---
id: oul652
title: 'The run detail cockpit: header, timeline, step rail, and terminal states'
state: done
assignee: agent
priority: medium
depends_on:
    - 1q7qp8
    - it3m03
    - qmnvgr
    - 5rkj33
    - tls69i
parent: 9gea5p
created: 2026-08-14T07:44:24Z
updated: 2026-08-25T20:42:11Z
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

**agent** — 2026-08-25T20:27:56Z

Seams: the parent spec names HTTP and the Worker executor; this slice is the cockpit UI. Following the established frontend seam (5rkj33): pure functions for header/timeline/rail/banner/cancel/run-again/live-event reduction, read back with no DOM. StatusChip remains the only lifecycle renderer.

**agent** — 2026-08-25T20:42:03Z

Done. The run detail cockpit at /runs/[id].

Seams: pure frontend functions (presentation.ts, events.ts) read back with no DOM, matching 5rkj33. StatusChip remains the only lifecycle renderer (visual-language.test.ts).

What landed
- Header: workflow name, run id, Version, trigger, StatusChip, meta row (elapsed · automation · time with you · steps done · worker · timeout), failure_reason once terminal, ⚠ N steps drifted.
- Timeline from control_intervals: four kinds, proportional flex, markers (paused / you took control / handed back / resumed), legend. Waiting is wait-hatched; verifying is an accent stripe — the visual language has five hues and no teal token, so verifying reuses accent rather than adding a sixth.
- Step rail from the Version (or test-run draft_snapshot): number, label, editor sentence, duration, badges (drift, completed by you, selector failure, skipped, records, files). Expansion: error, ranked candidates (died/matched/untried), Re-pick link, screenshots, extracted data, that Step's log lines. Control bands between Steps.
- Live: SSE via streamRunEvents; step.started/finished tick the rail; reconnect refetches REST then resubscribes. No Last-Event-ID.
- Terminal banner: `succeeded in 0:39 · 8 of 8 steps · 24 records · 1 download`; failed names step, reason, skipped count, with Re-pick. Cancel: inline confirm of the boundary rule, then the cancelling band, then the terminal banner on run.status.
- Run again dialog prefilled with this Run's Variable values (secrets as LockedCell), startRun of the latest published Version.
- Pane holds placeholders until 2aybf8. Output tab stays on e181q4.

Decisions
- matched_candidate_rank is 0-indexed in the API; the badge is 1-indexed (`found on candidate 3/5` for rank 2 of 5). Drift is any rank > 0.
- cancelling is not a RunStatus: the chip maps cancel_requested_at on a non-terminal Run to the cancelling LifecycleState.
- Re-pick href is `/workflows/{id}/editor?repick={stepId}` so m6s5me can honor it; repair stays in the editor.
- The Run again dialog lives on this screen. immifu's shared start dialog is a later consumer, not a blocker.
