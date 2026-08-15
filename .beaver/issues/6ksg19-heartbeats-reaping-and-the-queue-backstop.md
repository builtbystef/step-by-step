---
id: 6ksg19
title: Heartbeats, reaping, and the queue backstop
state: todo
priority: medium
depends_on:
    - 6ewr2p
parent: 9gea5p
created: 2026-08-14T07:41:34Z
updated: 2026-08-14T07:41:34Z
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
