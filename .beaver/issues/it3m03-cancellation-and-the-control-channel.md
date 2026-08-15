---
id: it3m03
title: Cancellation and the control channel
state: todo
priority: medium
depends_on:
    - 6ewr2p
parent: 9gea5p
created: 2026-08-14T07:42:07Z
updated: 2026-08-14T07:42:07Z
---

## What to build

How commands reach a Worker, and the one command that must never do damage. Commands travel two ways and the row is the authority: the backend stamps the request on the Run row and publishes it on the Run's Redis control channel; the Worker acts on the message when it arrives and re-reads the row at every Step boundary regardless — a dropped pub/sub message costs latency, never correctness. The boundary is the only place automation yields; an action in flight always completes. The Worker also checks between candidate-walk iterations inside a resolve loop, where nothing has been clicked yet.

```
POST /api/runs/{id}/cancel        → 202
GET  /internal/runs/{runId}/control → 200 {cancel_requested, pause_requested,
                                           takeover_phase, auto_handback_disabled}
```

Cancelling a `running` Run stamps `cancel_requested_at` and answers 202 with the status still `running` — the API never fakes a stop the Worker has not made. The Worker stops at the next boundary, marks the remaining Steps `skipped`, and ends the Run `cancelled`. (The `queued` case landed with the store slice; the `waiting_for_human` case lands with takeover.)

## Acceptance criteria

- [ ] Cancel a `running` Run → 202, `cancel_requested_at` set, status still `running` until the Worker acts.
- [ ] A cancellation requested while a Step is mid-action → that Step's Step Result is complete, never truncated; later Steps are `skipped`; the Run ends `cancelled`.
- [ ] With the control channel silenced (no publish), the Worker still honors a cancel written to the row at the next boundary — the row alone is sufficient.
- [ ] A cancellation requested during a long resolve loop takes effect between candidate iterations, before any action fires.
- [ ] The internal control read requires the shared token and reflects the row's request flags.
- [ ] Cancel on a terminal Run is rejected cleanly.
