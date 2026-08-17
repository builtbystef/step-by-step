---
id: f53mo0
title: 'Prefactor: Redis, Garage, and the Worker container in compose'
state: todo
priority: high
depends_on:
    - h9gene
parent: 9gea5p
created: 2026-08-14T07:40:47Z
updated: 2026-08-17T04:14:02Z
---

## What to build

The ground every execution slice stands on. Redis (the dispatch pipe and event bus) and Garage (the Artifact store) join the compose stack beside Postgres. The Worker becomes a real package in the monorepo, covered by the same four check commands as every other package. Its container image carries what a Run needs: Playwright with headed Chromium, an X display (Xvfb), a VNC server (x11vnc), and a minimal window manager for the browser's own dialogs and popups. The VNC server binds to the compose network only — never published to the host. The shared internal library takes shape: the seam through which Workers write Step Results, log lines, control intervals, artifact rows, and Run status directly to Postgres, and publish events directly to Redis — Workers never route writes through the backend.

No dispatch, no executor yet: the Worker process starts, connects to Redis and Postgres, reports itself in its logs, and idles.

**On Garage** (the store chosen on 2026-08-16, replacing MinIO — px25yw carries the reasoning). Image `dxflrs/garage`, S3 API on `:3900`, admin on `:3903`, a mounted `garage.toml` and a named volume for its data — without one, the store is wiped when the container terminates. Since v2.3.0 a single node bootstraps itself with `garage server --single-node --default-bucket` reading `GARAGE_DEFAULT_ACCESS_KEY` / `GARAGE_DEFAULT_SECRET_KEY` / `GARAGE_DEFAULT_BUCKET`, so no init sidecar is needed. `garage.toml` also wants an `rpc_secret` and an `admin_token`.

**Two endpoints, not one.** Workers reach the store at its compose hostname, but the presigned URL the backend mints in `tls69i` is followed by the *user's browser*, which cannot resolve that hostname. So the signing endpoint is configured separately from the internal one — an `S3_PUBLIC_ENDPOINT` beside `S3_ENDPOINT_URL` — or object reads route through the Next proxy. Getting this wrong passes every in-network test and breaks every real download, so the criteria below check it from outside the compose network.

## Acceptance criteria

- [ ] `docker compose up` brings up Postgres, Redis, Garage, the backend, and at least one Worker; the Worker's log shows a successful connection to both Redis and Postgres, an open X display, and a VNC server listening.
- [ ] The VNC port is reachable from another compose service and not from the host.
- [ ] The Worker package participates in the root check and test commands; a deliberate type error in it fails the check from the repository root.
- [ ] The shared internal library is importable from both the backend and the Worker package, and owns the database connection setup the Worker uses.
- [ ] Garage is reachable from the Worker container with credentials from the compose environment; a smoke test writes and reads one object through boto3 (not the `minio` SDK — the store is reached over plain S3, so it stays swappable).
- [ ] The bucket exists after a cold `docker compose up` with no manual step, and its objects survive `docker compose down && docker compose up`.
- [ ] A presigned GET minted with the public endpoint configuration fetches the smoke-test object **from the host**, outside the compose network, and returns 403 or 404 after it expires.
- [ ] Scaling to two Workers (compose scale) brings up two independent displays and VNC servers with no port collision.

## Notes

**claude** — 2026-08-17T04:04:21Z

Boundary pin (ADR 0004): the shared internal library carries database setup, models, and the event-publish helper only — the envelope-encryption/vault module stays in the backend package and never ships in the Worker image. Operational: pre-pull postgres, redis, and dxflrs/garage and budget the Worker image build (Playwright + Xvfb + x11vnc) against the loop's per-iteration timeout when this slice runs unattended.

**claude** — 2026-08-17T04:14:02Z

Execution-environment pin (loop operator's decision): this ticket runs as a supervised HOST session — it builds and runs container images, which the sandbox cannot. Later executor slices do not rebuild the Worker image per ticket: their tests run at the Python seam inside the sandbox against the host stack. The pre-pull advice in the earlier note applies to the host session.
