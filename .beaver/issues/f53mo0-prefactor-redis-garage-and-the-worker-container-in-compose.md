---
id: f53mo0
title: 'Prefactor: Redis, Garage, and the Worker container in compose'
state: done
assignee: claude
priority: high
depends_on:
    - h9gene
parent: 9gea5p
created: 2026-08-14T07:40:47Z
updated: 2026-08-18T07:20:35Z
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

**claude** — 2026-08-18T07:20:35Z

Done. The stack, the Worker package and its image, and the shared internal library are in place. No dispatch and no executor, as the ticket specified — the Worker proves its world, says so, and idles.

**What landed**

- `compose.yaml` gained **redis** (redis:8), **garage** (dxflrs/garage:v2.3.0), **api**, and **worker**. An `x-stack-environment` anchor is the single place that says how the services address each other inside the network. Garage runs `garage server --single-node --default-bucket` against a mounted `compose/garage.toml`, with named volumes for its metadata and its data; `GARAGE_RPC_SECRET` and `GARAGE_ADMIN_TOKEN` arrive as environment variables so no credential sits in a committed file. Healthcheck is the binary's own `/garage status`, since the image carries no shell.
- **`packages/core` (`step-by-step-core`)** — the shared internal library, a uv workspace member with the same four check scripts as every other package. `db` (`Base`, `get_engine()`, `session_scope()`, `get_session()`), `bus` (`get_redis()`), `objects` (`object_store()`, `signing_store()`, `artifact_bucket()`). Every URL and credential comes from the environment and nowhere else; every client is built on first use and cached one per process.
- **`apps/worker` (`step-by-step-worker`)** — `readiness.report()` runs the startup checks, logs what each found, and raises `NotReady` if any failed; `checks.py` holds the five real ones; `main.py` reports and then idles until SIGTERM. Its image carries Playwright with headed Chromium (151.0.7922.34), Xvfb, x11vnc, openbox, and xdpyinfo. `entrypoint.sh` starts the desktop, waits for the display rather than racing it, and execs the Worker.
- `step_by_step_api.db` now holds only `SessionDep`; `alembic/env.py` takes `Base` from core. `apps/api/Dockerfile` puts the backend in the stack.
- CI's `integration` job starts `postgres redis garage` with `docker compose up -d --wait` instead of service containers. Root `test:integration` fans out to api and core. `docs/ARCHITECTURE.md` and `AGENTS.md` updated.

**Decisions**

- **Garage's host port is 3910, not 3900** — and this was not hypothetical: another project on this machine already publishes 3900, exactly as it holds 5432 and 6379. Redis takes 6380 and the containerised backend takes 8001, so it coexists with `pnpm dev`'s host backend on 8000. Every one is overridable.
- **The object store lives in core, not in the Worker.** The ADR-0004 boundary pin lists what core carries; its purpose was to keep the envelope-encryption/vault module out of the Worker image, which still holds (verified: `step_by_step_api` is absent from the Worker image). The store went in beside `db` and `bus` because the backend signs URLs and the Worker writes objects, and the two-endpoint rule has to be stated once or the bug the ticket warns about comes straight back.
- **`signing_store()` beside `object_store()`, path-style addressing on both.** The internal client reads and writes at `S3_ENDPOINT_URL`; the signing client mints presigned URLs against `S3_PUBLIC_ENDPOINT`. Virtual-host addressing would put the bucket in the hostname, which no browser resolves for a compose service.
- **Openbox, not fluxbox.** Fluxbox insists on setting a root wallpaper; with no wallpaper setter installed it parks an `xmessage` error dialog on the display permanently — a window that would sit in every VNC frame and every screenshot Artifact. Neither `session.screen0.rootCommand` nor a `background: none` style suppressed it in 1.3.7. Openbox manages windows and nothing else.
- **The VNC server takes no password today**, deliberately. It is unreachable from anywhere but the compose network, and the view-only/control credential pair is `5yu03g`'s, along with the proxy that authenticates with it. Wiring half of that mechanism here would have pre-decided the other half.
- **Base images pinned to `ghcr.io/astral-sh/uv:0.12.3-python3.14-trixie-slim`** — the uv the root `pyproject.toml` requires. The floating tag ships 0.12.5 and `uv sync` refuses outright, which is the pin doing its job.
- **New production dependencies, all named in 9gea5p's Dependencies section**: `boto3` (S3 against a configurable endpoint, so the store stays swappable — not the `minio` SDK), `redis` (the dispatch pipe and event bus; no task framework, per px25yw and ADR 0002), `playwright` (the Worker's browser). `sqlalchemy` and `psycopg[binary]` moved from the api to core rather than being added.

**Facts a reviewer needs**

- **An expired presigned URL returns 400, not 403 or 404.** Garage answers `InvalidRequest: Date is too old` where AWS S3 answers 403. The criterion's intent holds — the URL stops serving the object — so the test asserts the refusal and that the body is not the object, rather than one store's status code. `tls69i` should not assume 403 when it maps this error.
- Criterion by criterion, on a stack cold-started from the committed files: the Worker's log shows `redis: PONG from redis:6379`, `postgres: PostgreSQL 17.11`, `display: :99, 1280x1024`, `vnc: port 5900, RFB 003.008`, `artifact store: bucket 'artifacts', wrote and read one object`. VNC answers `RFB 003.008` from the api container and is refused from the host, with no published port. A deliberate type error in `apps/worker` makes root `pnpm check` exit 1; removing it returns 0. Core imports in both containers from the same files. The bucket exists after `down -v` + `up` with no manual step, and an object written before `down` reads back after `up`. A presigned GET fetches from the host and is refused once expired. `--scale worker=2` gives two Workers, and an `xprop` property set on worker-1's root window is absent on worker-2's — genuinely separate displays, no port collision.
- Headed Chromium was launched inside the Worker container and openbox manages it: `_NET_CLIENT_LIST` carries the window titled `step by step - Google Chrome for Testing`. The display holds nothing else but openbox's own 1x1 helper windows.
- `pnpm run ci` passes; `openapi.json` and the generated client are unchanged, so the contract job stays clean. The fast tier is green with every service URL unset. `uv run pytest -m integration` — CI's exact invocation — passes 8 tests across both packages in one session.
- Not done, and not asked for: CI does not build the two images, so Dockerfile rot would only surface locally. Worth a ticket if the images start changing often.
- For the loop operator: `pnpm test:integration` now needs `REDIS_URL` and the `S3_*` variables as well as `DATABASE_URL` — load `.env` rather than exporting `DATABASE_URL` alone.
