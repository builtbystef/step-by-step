---
id: qmnvgr
title: 'Takeover: pausing, waiting, and hand-back'
state: todo
priority: medium
depends_on:
    - 6ewr2p
    - 1q7qp8
    - it3m03
parent: 9gea5p
created: 2026-08-14T07:42:54Z
updated: 2026-08-14T07:43:06Z
---

## What to build

The Run parking for a human. Entering `waiting_for_human` happens on either of: a `pause-for-takeover` Step — the Run parks *before* the Step's work, with the Step's author-written message; or a user pause request (`POST /api/runs/{id}/pause`), honored between resolve-loop iterations of the stuck Step, so its action has not started. On entry the Worker opens a `waiting` control interval and stamps the takeover deadline — the Workflow's takeover timeout (default 30 minutes) or the Step's override. One clock covers waiting plus human control plus verifying: the countdown never restarts.

Control endpoints:

```
POST /api/runs/{id}/takeover  → 200 {ticket, ws_url, expires_at, deadline_at}
                                409 code=not_waiting | code=already_held
POST /api/runs/{id}/handback  → 202
POST /api/runs/{id}/takeover/abandon → 202
```

The takeover ticket is single-use and short-TTL, and the holding session is recorded — one session holds control at a time. While a `human` interval is open the Worker suspends automation entirely. This slice covers the manual hand-back path (no success check): hand-back opens a `verifying` interval and automation resumes by retrying the paused Step with a fresh timeout budget (`completed_by_human` semantics belong to the success-check slice). Abandon → `failed` / `takeover_abandoned`. The deadline passing in any phase (via the loop's tick) → `failed` / `takeover_timeout`, browser closed. Cancelling a `waiting_for_human` Run ends the takeover and closes the browser immediately — nothing is in flight. Waiting/human/verifying time never counts toward the run timeout. The VNC transport and all UI arrive in later slices; this slice is the executor and API semantics, asserted at both seams.

## Acceptance criteria

- [ ] A `pause-for-takeover` Step → run `waiting_for_human` before the Step acts, a `waiting` interval open, the browser alive, `deadline_at` = the default takeover timeout; a Step-level override changes it.
- [ ] `POST pause` on a Run stuck resolving → the Run parks between candidate iterations with no action fired.
- [ ] Takeover on a `running` Run → 409 `not_waiting`; on a waiting Run → a ticket; a second session's call → 409 `already_held`; the same ticket redeemed twice → the second refused.
- [ ] Taking control opens a `human` interval; the deadline is unchanged from the `waiting` phase (one clock).
- [ ] Hand-back (no success check) → a `verifying` interval, then the paused Step retried with a fresh timeout budget rather than skipped; when it passes, the Run continues.
- [ ] Abandon during control → `failed` / `takeover_abandoned`; the pause Step `failed`, later Steps `skipped`.
- [ ] A waiting Run past its deadline, then one tick → `failed` / `takeover_timeout`; the same for a Run whose user took control and sat past the deadline.
- [ ] Cancel of a waiting Run → `cancelled` immediately, browser closed, no boundary wait.
- [ ] A Run that waited 10 minutes then ran 2 → `automation_ms` reflects only the 2; the intervals table carries the whole story.

