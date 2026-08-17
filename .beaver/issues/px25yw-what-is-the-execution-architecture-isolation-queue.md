---
id: px25yw
title: 'What is the execution architecture: isolation, queue semantics, streaming, pause/resume?'
state: done
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
updated: 2026-08-17T01:01:26Z
---

One live interview (grill-me). With scope (8iuuh8), takeover mechanics (1ar6xu), and auth-state constraints (u7nkwh) known, decide:

- Worker isolation: container per run vs. pooled processes; what the takeover mechanism requires here.
- Queue semantics on Redis: job shape, retries, timeouts, concurrency limits, scheduled-run dispatch.
- Progress streaming to the frontend: SSE vs. WebSocket, what streams (step status, screenshots, logs), and the fan-out path (worker → backend → client).
- Pause/takeover/resume as run states: how a run suspends, holds the browser alive, and resumes.
- Artifact write path from workers.

The answer gates the second spec area (backend + workers + live run).

## Notes

**claude** — 2026-08-10T03:34:07Z

Answers (interview 2026-08-09):

WORKER MODEL — A fixed pool of identical long-lived Worker containers (docker compose replicas); each executes at most one Run at a time. Total Run concurrency = pool size; excess Runs wait in `queued`. No dynamic container-per-run spawning: the backend never needs Docker-socket privileges, and compose-friendliness wins for a self-hosted product. Each Run gets a fresh headed Chromium process with a throwaway profile directory — no state bleed between users' Runs (auth-state blobs are bearer credentials, u7nkwh), and one browser per X11 display matches the VNC takeover mechanism (1ar6xu).

QUEUE — Redis (a container in the compose stack; a managed/Upstash Redis was considered and retracted) is a dumb dispatch pipe; Postgres is the source of truth. The job payload is a Run id only; the Worker loads the Version, Variables, and secrets from Postgres. Queue library: implementer's choice within this shape (arq or a hand-rolled blocking pop; nothing Celery-scale). Scheduled dispatch: a scheduler loop in the backend queries Postgres every minute for due Schedules, creates Run rows, and enqueues their ids — no Redis-side delayed jobs, no separate beat process. Missed-run/overlap policy stays on the Frontier.

RETRIES — No automatic Run-level retries, ever (ADR 0002): Runs act on external websites and replay is not idempotent. Retrying exists only inside a step (Playwright actionability waits) — wljln8's domain.

RUN STATE MACHINE — queued → running ⇄ waiting_for_human; terminal: succeeded | failed | cancelled. Six states; a machine-readable failure_reason carries the nuance: step_failed, takeover_timeout, run_timeout, worker_lost, and the auth/challenge classification u7nkwh called for. Cancellation is allowed in any non-terminal state: queued → removed before dispatch; running → the Worker aborts at the next step boundary (never mid-action); waiting_for_human → the takeover ends and the browser closes. Cancelling a Batch cancels its current Run and skips the remaining rows.

TIMEOUTS — A per-Workflow run timeout, default 30 minutes, counting automation time only; the waiting_for_human clock is the separate ~30-minute takeover timeout (8iuuh8). Exceeding it → failed/run_timeout.

STREAMING — Workers publish events (run/step status changes, log lines, screenshot-ready notices) to Redis pub/sub; the backend fans out to clients over SSE. Commands (start, cancel, request/end takeover) travel over plain REST. Screenshot bytes are never pushed through the stream — clients fetch them as Artifacts by URL. The interactive takeover view is a separate channel entirely (VNC).

TAKEOVER PLUMBING — A waiting_for_human Run keeps its Worker and live browser; parked Runs occupying pool slots until resume or timeout is an accepted v1 cost (no reserved takeover pool). The backend proxies the VNC WebSocket: one public endpoint, the backend authenticates the user and checks Run ownership, then pipes to the owning Worker. Workers are never internet-facing.

LIVENESS — Each Worker heartbeats its current Run's row every few seconds; the backend scheduler loop doubles as the reaper, marking any running/waiting_for_human Run with a stale heartbeat failed/worker_lost.

DATA ACCESS & ARTIFACTS — Workers access Postgres directly via a shared internal library (first-party trusted code in one deployment; only the secrets boundary may be revisited, in 7o0nmx). Workers write Artifacts directly to S3-compatible storage (MinIO in the compose stack) and insert the Artifact rows in Postgres themselves. Artifact bytes stay out of the backend's request path and out of Postgres.

Deployment shape confirmed in passing: the entire stack is self-hosted docker compose — backend, Workers, Postgres, Redis, MinIO. Glossary: Worker added. ADR: docs/adr/0002-no-automatic-run-retries.md.

**claude** — 2026-08-17T01:01:26Z

SUPERSEDED IN PART (2026-08-16): the Artifact store is GARAGE, not MinIO. Everything else this node settled stands unchanged — S3-compatible object storage, Workers writing Artifacts directly and inserting their own rows, artifact bytes out of the backend's request path and out of Postgres, one self-hosted docker compose stack.

Reason: MinIO put its community edition into maintenance mode in December 2025, marked the repository "NO LONGER MAINTAINED" on 2026-02-12, and archived it read-only on 2026-04-25. The AGPLv3 licence did not change — the code was abandoned, not relicensed. No further releases, reviewed patches, official community binaries, or security patches. Engineering moved to AIStor, the paid product.

Garage (Deuxfleurs, AGPLv3, garagehq.deuxfleurs.fr) replaces it. It is purpose-built for exactly this scale — self-hosted, single node, too small for Ceph. S3 API on :3900, admin on :3903. Since v2.3.0 a single node bootstraps itself: `garage server --single-node --default-bucket` with GARAGE_DEFAULT_ACCESS_KEY / GARAGE_DEFAULT_SECRET_KEY / GARAGE_DEFAULT_BUCKET, so the compose stack needs no init sidecar (MinIO needed an `mc` one).

It covers every S3 feature this project uses: presigned URLs, multipart upload, CORS, ListObjectsV2, explicit DELETE. It lacks object versioning, bucket policies, object lock and server-side encryption — none of which this project uses; retention here is app-driven (9gea5p: none in v1, DELETE purges).

Considered and rejected: SeaweedFS (Apache 2.0, larger community, fine choice — Garage won on footprint and on being one conceptual unit rather than master/volume/filer); RustFS (Apache 2.0, markets itself as a drop-in MinIO replacement, but still alpha/early-beta and its own docs say not for production).

No ADR: docs/adr/README.md requires a decision to be hard to reverse, and this one is one compose service plus an endpoint URL — the code depends on the S3 API, never on the vendor. Recorded as a stack fact on ymz3md instead.
