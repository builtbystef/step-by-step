---
id: f53mo0
title: 'Prefactor: Redis, MinIO, and the Worker container in compose'
state: todo
priority: high
depends_on:
    - h9gene
parent: 9gea5p
created: 2026-08-14T07:40:47Z
updated: 2026-08-14T07:40:47Z
---

## What to build

The ground every execution slice stands on. Redis (the dispatch pipe and event bus) and MinIO (the Artifact store) join the compose stack beside Postgres. The Worker becomes a real package in the monorepo, covered by the same four check commands as every other package. Its container image carries what a Run needs: Playwright with headed Chromium, an X display (Xvfb), a VNC server (x11vnc), and a minimal window manager for the browser's own dialogs and popups. The VNC server binds to the compose network only — never published to the host. The shared internal library takes shape: the seam through which Workers write Step Results, log lines, control intervals, artifact rows, and Run status directly to Postgres, and publish events directly to Redis — Workers never route writes through the backend.

No dispatch, no executor yet: the Worker process starts, connects to Redis and Postgres, reports itself in its logs, and idles.

## Acceptance criteria

- [ ] `docker compose up` brings up Postgres, Redis, MinIO, the backend, and at least one Worker; the Worker's log shows a successful connection to both Redis and Postgres, an open X display, and a VNC server listening.
- [ ] The VNC port is reachable from another compose service and not from the host.
- [ ] The Worker package participates in the root check and test commands; a deliberate type error in it fails the check from the repository root.
- [ ] The shared internal library is importable from both the backend and the Worker package, and owns the database connection setup the Worker uses.
- [ ] MinIO is reachable from the Worker container with credentials from the compose environment; a smoke test writes and reads one object.
- [ ] Scaling to two Workers (compose scale) brings up two independent displays and VNC servers with no port collision.
