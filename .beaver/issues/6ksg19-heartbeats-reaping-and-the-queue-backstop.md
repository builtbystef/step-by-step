---
id: 6ksg19
title: Heartbeats, reaping, and the queue backstop
state: done
assignee: agent
priority: medium
depends_on:
    - 6ewr2p
parent: 9gea5p
created: 2026-08-14T07:41:34Z
updated: 2026-08-25T18:02:08Z
---

## What to build

Pool self-recovery. The Worker heartbeats its Run's row every few seconds over the internal route (shared compose token, 54i6da's posture):

```
POST /internal/runs/{runId}/heartbeat  {worker_id, vnc_endpoint} → 204
                                         409 code=run_terminal    (the Worker aborts the Run)
```

And the backend's minute loop gains its reap-and-backstop duties, written so a tick is a plain function the tests invoke directly: any non-terminal Run whose heartbeat is stale is marked `failed` / `worker_lost` with `skipped` Step Results written for whatever the Run never reached; any Run still `queued` past a threshold with no worker assigned is re-enqueued — a duplicate id on the list is harmless because the conditional claim rejects it.

## Acceptance criteria

- [ ] A running executor's Run row shows `heartbeat_at` advancing every few seconds.
- [ ] Heartbeat without the shared token → 401; for a terminal Run → 409 `run_terminal`, and the Worker abandons the Run and closes its browser.
- [ ] A Run whose `heartbeat_at` is older than the threshold, then one tick → `failed` / `worker_lost`, and every unreached Step has a `skipped` Step Result.
- [ ] A Run `queued` past the threshold with no worker, then one tick → its id is back on the list; a Run within the threshold is left alone.
- [ ] The re-enqueued id arriving twice → executed exactly once (the second claim updates zero rows).
- [ ] A healthy running Run is untouched by a tick.

## Notes

**agent** — 2026-08-25T17:47:48Z

Test seams from the parent spec: the backend HTTP API plus tick() invoked directly against Postgres and Redis (heartbeat auth/advancement, reap, queue backstop, duplicate claim), and the Worker executor against fixture pages (periodic heartbeat, abandon-and-close on 409). The Worker's heartbeat HTTP client is tested at its own POST surface against a local server.

**agent** — 2026-08-25T18:02:04Z

Completed pool self-recovery.

Backend: POST /internal/runs/{id}/heartbeat authenticates with INTERNAL_TOKEN (Bearer; 54i6da's shared compose token) and stamps heartbeat_at / worker fields on a live assigned Run, or 401 without the token / 409 run_terminal otherwise. The route is out of the generated client. tick() now reaps running/waiting_for_human Runs whose heartbeat_at is older than 90s to failed/worker_lost and writes skipped Step Results for unreached Steps; queued Runs older than 60s with no worker are LPUSHed again.

Worker: the executor pulses every 5s; a 409 abandons the Run, closes the browser, and does not overwrite the already-terminal row. Dispatch wires the stdlib HTTP client when API_URL and INTERNAL_TOKEN are set.

Decisions: INTERNAL_TOKEN in the shared compose anchor (dev default dev-internal-token); API_URL=http://api:8000 on the worker service; thresholds 5s / 90s / 60s; unknown/queued/unassigned heartbeats share 409 run_terminal so the Worker stops. No new production dependency.

Verified: ruff + ty on the touched packages; pytest fast tier; integration test_heartbeats + test_schedules; browser test_executor. pnpm check/test via uv run could not be invoked in this sandbox (uv tries to re-fetch croniter and DNS is down); the same tools were run from .venv.
