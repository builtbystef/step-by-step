---
id: 1q7qp8
title: 'Events: Redis pub/sub, SSE fan-out, and log lines'
state: todo
priority: high
depends_on:
    - 6ewr2p
parent: 9gea5p
created: 2026-08-14T07:41:51Z
updated: 2026-08-17T04:03:47Z
---

## What to build

The live wire from Worker to browser tab. Workers publish to `run:{id}:events` on Redis pub/sub; the backend subscribes and fans out over SSE. Commands travel over REST, never the stream; screenshot and trace bytes never enter the stream — an event announces, the client fetches. The event vocabulary:

```
GET /api/runs/{runId}/events   (SSE)

run.status    { run_id, status, failure_reason?, failure_detail?, at }
step.started  { run_id, step_id, position, at }
step.finished { run_id, step_id, status, matched_candidate_rank, candidate_count,
                completed_by_human, extracted_count?, at }
control       { run_id, phase: "automation"|"waiting"|"human"|"verifying",
                deadline_at?, at }
predicate     { run_id, met: bool, grace_ends_at?, at }
diagnostic    { run_id, step_id, kind: "suspected_challenge", detail, at }
log           { run_id, seq, step_id?, level, text, at }
artifact      { run_id, step_id?, artifact_id, kind, at }
```

Reconnection replays nothing: a client that reconnects refetches the Run over REST — everything is in Postgres — and subscribes from now on. No event buffer, no Last-Event-ID; a second source of truth would only be a way to disagree with Postgres. The executor emits `step.started`/`step.finished`/`run.status` as it walks, and its log lines land twice by design: a `run_log_lines` row and a `log` event, through one publish helper. The cap: 10 000 lines per Run, one final `log truncated` line, further lines dropped, never buffered. The read side:

```
GET /api/runs/{runId}/logs?after_seq=&step_id=  → 200 [LogLine]
```

## Acceptance criteria

- [ ] Watching a Run over SSE while the executor drives a three-Step Version → `step.started`/`step.finished` for each Step in order, then a terminal `run.status` — each exactly once.
- [ ] A log line published by the executor arrives as an SSE `log` event and as a `run_log_lines` row with the same seq.
- [ ] Disconnecting mid-Run and reconnecting → the stream delivers only events published after the reconnect; the REST detail fetch carries everything missed.
- [ ] 10 001 published lines → 10 000 stored rows plus the truncation line, and the logs endpoint's last line says truncated.
- [ ] `after_seq` returns only later lines; `step_id` returns only that Step's lines.
- [ ] The SSE route enforces Run ownership: another user's Run id → 404 before any subscription.
- [ ] No event carries artifact bytes — an `artifact` event carries ids only.

## Notes

**claude** — 2026-08-17T04:03:47Z

Re-scope per ADR 0005: the SSE route's ownership check is the org Membership gate — another Organization's Run id → 404; any member of the Run's Organization may subscribe.
