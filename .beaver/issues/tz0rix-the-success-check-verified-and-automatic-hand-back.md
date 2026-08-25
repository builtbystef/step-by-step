---
id: tz0rix
title: 'The success check: verified and automatic hand-back'
state: done
assignee: agent
priority: medium
depends_on:
    - qmnvgr
parent: 9gea5p
created: 2026-08-14T07:43:25Z
updated: 2026-08-25T19:11:27Z
---

## What to build

The part that makes hand-back trustworthy. Where a `pause-for-takeover` Step carries a `successCheck` Target (the document field d8ux2s's store holds), the Worker polls it while the Run waits and while the human is in control — a read-only resolve, never an action, safe alongside human input — and its live met/unmet state streams as `predicate` events.

During control, the check becoming met starts a 6-second grace countdown and control hands back automatically. "Hand back now" skips the grace; "stay in control" (`POST /api/runs/{id}/takeover/hold {auto_handback: bool}`) disables auto hand-back for the remainder of that takeover — the grace exists so a site that chains a second prompt does not yank control away mid-task. On hand-back the `verifying` interval consults the check: met → automation resumes at the next Step, the pause Step's result `passed` with `completed_by_human`; unmet → the Run does not resume — it returns to `waiting`, the browser stays held, and the user chooses a fresh takeover ("keep control and finish it") or gives up (abandon → `failed` / `takeover_abandoned`). Where the check is absent — always the case for a heuristic pause — hand-back stays manual-only, as landed before.

## Acceptance criteria

- [ ] While a Run waits on a pause Step with a `successCheck`, `predicate` events stream its state; a fixture page flipping the element into existence flips the event to met.
- [ ] The check becoming met during control → a `predicate` event with `grace_ends_at`, and roughly 6 seconds later control ends and automation resumes with no user action.
- [ ] `takeover/hold {auto_handback: false}` before the grace expires → control is kept; the check staying met never hands back for the rest of that takeover.
- [ ] Hand-back with the check met → a `verifying` interval, then automation resumes at the next Step, and the pause Step's result is `passed` with `completed_by_human`.
- [ ] Hand-back with the check unmet → the Run returns to `waiting` without advancing; a fresh takeover is possible; abandoning yields `failed` / `takeover_abandoned`.
- [ ] The one-clock rule holds through all of it: waiting → control → unmet hand-back → waiting consumes one deadline, and passing it in any phase → `takeover_timeout`.
- [ ] A pause Step without a `successCheck` behaves exactly as before: no predicate events, manual hand-back, the paused Step retried.

## Notes

**agent** — 2026-08-25T18:58:55Z

Seams from the parent spec: (1) backend HTTP against Postgres and Redis for POST /api/runs/{id}/takeover/hold {auto_handback}, 409 not_waiting / not_held, auto_handback_disabled on the row and on GET /internal/runs/{id}/control, deadline unchanged; (2) the Worker executor against Playwright fixture pages for predicate events while waiting and during control, the 6s grace and auto hand-back, hold disabling auto for the rest of that takeover, met hand-back advancing with completed_by_human, unmet hand-back returning to waiting on the same deadline, and a pause without a successCheck staying manual-only.

**agent** — 2026-08-25T19:11:26Z

Completed the success check and automatic hand-back.

API: POST /api/runs/{id}/takeover/hold {auto_handback} sets auto_handback_disabled for the rest of that takeover (409 not_waiting / not_held). GET /internal/runs/{id}/control already exposes the flag. release_holder clears the holder, the hand-back stamp, and the hold flag without restamping takeover_deadline_at, so a fresh takeover is possible on the same clock.

Worker: while parked on a pause Step with a successCheck, a read-only one-walk resolve publishes predicate events (initial state, changes, and grace_ends_at when the check becomes met during control). A met check starts a 6s grace and hands back unless hold disabled auto. Hand-back with the check met writes the pause Step passed / completed_by_human and resumes at the next Step; unmet returns to waiting on the same deadline; no check stays manual-only and retries the paused Step.

OpenAPI and the generated client include holdTakeover.
