---
id: px25yw
title: 'What is the execution architecture: isolation, queue semantics, streaming, pause/resume?'
state: in-progress
assignee: claude
priority: high
labels:
    - roadmap:idnzwf
    - session:grill
depends_on:
    - 8iuuh8
    - 1ar6xu
    - u7nkwh
parent: idnzwf
created: 2026-08-08T07:08:04Z
updated: 2026-08-10T02:53:19Z
---

One live interview (grill-me). With scope (8iuuh8), takeover mechanics (1ar6xu), and auth-state constraints (u7nkwh) known, decide:

- Worker isolation: container per run vs. pooled processes; what the takeover mechanism requires here.
- Queue semantics on Redis: job shape, retries, timeouts, concurrency limits, scheduled-run dispatch.
- Progress streaming to the frontend: SSE vs. WebSocket, what streams (step status, screenshots, logs), and the fan-out path (worker → backend → client).
- Pause/takeover/resume as run states: how a run suspends, holds the browser alive, and resumes.
- Artifact write path from workers.

The answer gates the second spec area (backend + workers + live run).
