# Architecture

The modules of this system, and the seams between them. Update this file when the shape changes. Audits compare it with reality.

## Layout

A two-language monorepo, scaffolded from the user's `alloy` template (issue `ymz3md` records the interview that chose it). pnpm + Vite+ (`vp`) run the TypeScript side; uv + ruff + ty + pytest run the Python side. Node and Python versions are pinned in `.node-version` and `.python-version`.

```text
├── apps/
│   ├── api/            # FastAPI backend (Python package: step_by_step_api)
│   │   ├── alembic/    # migrations
│   │   └── Dockerfile  # the backend's compose image
│   ├── worker/         # the Worker (Python package: step_by_step_worker)
│   │   ├── Dockerfile  # Playwright + Chromium + Xvfb + x11vnc + openbox
│   │   └── entrypoint.sh
│   └── web/            # Next.js frontend
├── packages/
│   ├── core/           # step-by-step-core — the shared internal library
│   └── api-client/     # @step-by-step/api-client — generated from the OpenAPI schema
├── compose/            # configuration the stack's services mount (garage.toml)
├── tsconfig/           # shared TypeScript presets (base/node/browser/library)
├── pnpm-workspace.yaml # TS workspace + supply-chain policy
└── pyproject.toml      # uv workspace + ruff/ty/pytest config
```

The Python packages register in the root `pyproject.toml`'s `[tool.uv.workspace]` and each carries a `package.json` with the four check scripts, which is how `vp` fans the one command vocabulary out over both languages.

One package is decided but not yet built:

- `apps/extension` — the MV3 recording extension. The workspace globs and `vp check`/`vp test` cover it the moment it exists.

The deployment shape (settled in `px25yw`): one docker compose stack — backend, Workers, Postgres, Redis, Garage. `compose.yaml` at the root holds all five; `docker compose up -d` starts them. `pnpm dev` still runs FastAPI and Next.js on the host for day-to-day frontend work, reaching the stack over its published host ports; the containerised backend is what a Worker and the VNC path talk to.

**Host ports are shifted, deliberately.** Postgres publishes on **5433**, Redis on **6380**, and Garage's S3 API on **3910** — not 5432, 6379, and 3900 — because another project on the same machine already holds all three. `POSTGRES_PORT`, `REDIS_PORT`, and `GARAGE_S3_PORT` override them; the backend container takes **8001** (`API_PORT`) so that it and `pnpm dev`'s host backend on 8000 coexist. `.env.example` carries the matching URLs. Inside the network the services answer to their own names on their native ports, and `compose.yaml`'s `x-stack-environment` anchor is the single place that says so.

The Workers publish **nothing**. Their VNC servers must be reachable from the backend over the compose network and from nowhere else, which is also what makes `docker compose up --scale worker=N` work: with no published port there is nothing for a replica to collide with, and each container's `:99` display is its own.

The stack is long-lived shared state: dev, the tests, and any sandboxed agent loop all reach the same containers, so nothing may assume it starts fresh.

Garage is the Artifact store, chosen over MinIO on 2026-08-16 after MinIO archived its community edition; `px25yw` carries the reasoning and `ymz3md` the stack fact. What binds code rather than compose: artifacts are read and written through the **S3 API only**, via boto3 against a configurable endpoint URL, so the store stays swappable. Garage has no object versioning, bucket policies, object lock, or server-side encryption — none are used here, since retention is app-driven and ADR 0003 puts encryption in the application layer.

It runs as a single self-bootstrapping node: `garage server --single-node --default-bucket` writes the one-node layout, the access key, and the bucket on first boot from the `GARAGE_DEFAULT_*` variables, so the stack needs no init sidecar and a cold `docker compose up` needs no manual step. `compose/garage.toml` is the mounted config; the `rpc_secret` and `admin_token` it would otherwise carry arrive as `GARAGE_RPC_SECRET` and `GARAGE_ADMIN_TOKEN` so that no credential sits in a committed file. Two named volumes hold its metadata and its data — without them the store is wiped whenever the container is replaced.

## Seams

### The typed API boundary

`apps/api`'s `build` dumps the FastAPI OpenAPI schema to `apps/api/openapi.json`; `packages/api-client`'s `build` regenerates a typed fetch client from it. Both the schema and the generated client are committed, so a fresh clone typechecks without running Python — and CI's `contract` job regenerates both and fails on any diff. The frontend imports only `@step-by-step/api-client`, never raw fetch paths. New FastAPI routes need an `operation_id`; it becomes the generated function name.

### The dev proxy

In dev the browser only talks to Next.js: `apps/web/next.config.ts` rewrites `/api/*` to `http://localhost:8000` (override with `API_URL`). No CORS setup exists, deliberately.

### The shared internal library

`packages/core` (`step-by-step-core`) is what the backend and the Workers both import. It exists because Workers do **not** route their writes through the backend (`px25yw`): a Worker writes Step Results, log lines, control intervals, artifact rows, and Run status straight to Postgres, and publishes its events straight to Redis. Those seams have to live somewhere both sides can reach.

Three modules, each owning one connection and nothing else:

- `step_by_step_core.db` — the database, below.
- `step_by_step_core.bus` — `get_redis()`, the process-wide client built from `REDIS_URL`. Redis is the dispatch pipe and the event bus; Postgres, never Redis, holds the truth.
- `step_by_step_core.objects` — the Artifact store, below.

What deliberately stays out: the envelope-encryption and vault module is the backend's alone and never ships in the Worker image (ADR 0004 — Workers never hold the master key).

### The database

SQLAlchemy 2 + Alembic, on psycopg 3 (`postgresql+psycopg://`). The connection URL comes only from the `DATABASE_URL` environment variable — `apps/api/alembic/env.py` sets it and `alembic.ini` carries no URL. Nothing defaults it in code, so a missing variable is a loud failure rather than a silent connection to the wrong database.

`step_by_step_core.db` is the seam:

- `Base` — the declarative base every table inherits; `alembic/env.py` autogenerates from its metadata.
- `get_engine()` — the process-wide engine, built on first use rather than at import, so the no-services tier and anything that merely imports the app need no database.
- `session_scope()` — one session for one unit of work, as a context manager. This is the form a Worker uses.
- `get_session()` — the same session as a generator, which is what FastAPI resolves as a dependency.

`step_by_step_api.db` adds only what is FastAPI's: `SessionDep`, the annotated dependency a route handler declares to receive its request's session. The session opens when the request starts and closes when it ends, rolling back whatever the handler did not commit. Handlers commit for themselves.

Migrations run with `pnpm --filter api run migrate` (`alembic upgrade head`). One revision exists — an empty baseline that gives the runner a head to reach; the accounts slice writes the first tables.

### The vault's encryption

`step_by_step_api.envelope` is the backend's alone — the one module deliberately kept out of `packages/core`, because the Workers that import core must never hold the master key (ADR 0004). It is envelope encryption per ADR 0003, PyNaCl `SecretBox` on both levels: `seal()` mints a fresh 32-byte data key per record, seals the plaintext under it and the data key under the master key, and returns the two blobs a vault row stores; `open_sealed()` reverses it; `rewrap()` re-seals a data key from one master key to another and leaves the plaintext untouched, reporting a record an earlier pass already moved so a half-finished rotation can be re-run rather than corrupted.

`master_key()` reads `STEPBYSTEP_MASTER_KEY` — base64 of 32 bytes — and is the only thing in the module that touches the environment; every other function takes the key it works with, which is what makes rotation a two-key call rather than a global swap. The backend's **lifespan calls it at startup**, so a missing, malformed, or wrong-length key stops the process while an operator is watching rather than failing on the first vault write. In `compose.yaml` the variable sits on the `api` service alone, outside the `x-stack-environment` anchor the Workers share.

### The mailer

`step_by_step_api.mail` is the one place email leaves the system. Callers say
`send(to, subject, text)` and never learn which adapter carried it; `MAILER`
picks that, `console` by default, and `MAIL_FROM` is the sender.

- **console** — logs the message and keeps it in an in-process outbox. It is
  what makes a dev instance work with no mail service, and it is the **test
  capture point**: the accounts seam tests read the Sign-in Code out of
  `outbox()` rather than out of the table that holds its hash.
- **smtp** — `smtplib` against `SMTP_HOST`/`SMTP_PORT` (587 by default),
  authenticating with `SMTP_USERNAME`/`SMTP_PASSWORD` when both are set and
  upgrading with STARTTLS when the server offers it. Offered-not-required, so
  that a relay on the instance's own host still works. It keeps self-hosting
  provider-free.
- **resend** — an HTTP POST to Resend with `RESEND_API_KEY`; the recommended
  hosted path.

The adapter is built once and **at startup**, from the lifespan beside the
master key: a mailer whose configuration is missing stops the boot with the
variable's name, rather than surfacing on the first person's sign-in — and the
Sign-in Code is the only way into an instance. The variables sit on the `api`
service alone in `compose.yaml`, outside the anchor the Workers share, because
the backend sends every email and a Worker sends none.

A failed send raises whatever the adapter's own library raises. v1 has no
caller that catches one, so nothing is wrapped to make them look alike.

### The Artifact store, and its two endpoints

`step_by_step_core.objects` is boto3 against a configurable endpoint, and it exposes **two** clients on purpose:

- `object_store()` reads and writes at `S3_ENDPOINT_URL` — the address a process inside the stack resolves (`http://garage:3900`).
- `signing_store()` mints presigned URLs against `S3_PUBLIC_ENDPOINT` — the address the _user's browser_ resolves, which is never a compose hostname.

They are the same value on a developer's host and different in a real deployment. Signing with the internal endpoint passes every in-network test and breaks every real download, which is why the rule lives in one module rather than in each caller. Addressing is path-style in both: virtual-host style would put the bucket in the hostname, which no browser can resolve for a compose service.

`artifact_bucket()` reads `S3_BUCKET`. Credentials and region come from `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, and `S3_REGION`.

### The Worker

`apps/worker` (`step_by_step_worker`) is a long-lived process with a desktop. Its image carries Playwright with headed Chromium, `Xvfb` for the display, `x11vnc` for the stream the takeover pane consumes, and `openbox` so the browser's own dialogs, popups, and file pickers behave. `entrypoint.sh` starts the three, waits for the display rather than racing it, and execs the Worker.

Openbox rather than fluxbox: it manages windows and nothing else. Fluxbox insists on setting a root wallpaper and, finding no wallpaper setter installed, parks an error dialog on the display — a window that would sit in every VNC frame and every screenshot Artifact.

At startup the Worker proves it can reach everything a Run needs — Redis, Postgres, its display, its VNC server, and the Artifact store, the last by a real write-read-delete round trip — logs what each check found, and refuses to start if any failed. Every check runs even after one fails, so one boot shows an operator every problem rather than one problem per boot. Then it idles: there is no dispatch and no executor yet.

The VNC server takes no password today. It is unreachable from anywhere but the compose network, and the view-only and control credentials the backend proxy authenticates with arrive with `5yu03g`, which owns the proxy that uses them.

### The frontend's visual language

`apps/web` is Tailwind CSS 4 with shadcn/ui generated against Base UI (`components.json` style `base-nova`), and TanStack Query for server state. The vocabulary lives in four places, and a screen inherits it rather than inventing one:

- `app/globals.css` — the only file that may name a colour. It defines the surfaces (`--bg`, `--panel`, `--ink`, `--mut`, `--line`) and the five-hue semantic ramp (`--accent` the machine is acting, `--wait` a human is needed, `--human` a secret, `--ok` succeeded, `--bad` failed), maps them onto shadcn's own token names so the generated components speak this palette and no second one, and sets the type scale to exactly six sizes. Spacing and radius are Tailwind's defaults untouched. There is no dark mode: the `dark:` variant is rebound to a class the app never sets, so a viewer's OS preference cannot half-apply a palette that does not exist.
- `components/ui/` — shadcn's, generated by its CLI and not hand-edited.
- `components/primitives/` — the eleven named primitives, one file each, and each the only place its idea is rendered.
- `lib/labels.ts` and `lib/copy.ts` — the single source of every state's wording, and the sentences two screens must say identically.

`lib/query-client.ts` builds the one QueryClient. `mutations.retry` is `false` because a retried Run start acts twice on a real website; query `retry` and `staleTime` are deliberately absent so each key chooses its own.

The shadcn CLI is run plainly — `pnpm dlx shadcn@latest add <component>` — and its output is taken as it comes: `shadcn` and `tw-animate-css` are project dependencies because `globals.css` imports `shadcn/tailwind.css` (the generated components' `data-open`, `data-closed`, `scroll-fade`, and `shimmer` definitions) and the animation utilities shadcn's overlays are written against. `semver` is listed in `trustPolicyExclude` in `pnpm-workspace.yaml` for it: shadcn pulls `@babel/core`, which pins `semver@^6.3.1`, a 2023 release that predates provenance and that `trustPolicy: no-downgrade` would otherwise refuse.

Three things the CLI writes are deliberately not kept, and a re-run will reintroduce all three:

- **Its colour palette.** `init` overwrites `--accent` and appends the neutral oklch set plus `chart-*` and `sidebar-*`. The ramp above is the only palette; a chart or sidebar token arrives with the first component that needs one.
- **Its `--radius` scale and its `.dark` block.** Radius is Tailwind's default, and there is no dark mode.
- **A webfont.** `init` adds Geist through `next/font/google`; the type scale is `system-ui`.

It also rewrites `lib/utils.ts`, which drops the tailwind-merge extension that teaches it the six font sizes. `lib/utils.test.ts` fails when that happens.

### Strictness

Both typecheckers run at full strict, set at scaffold time. TypeScript: the flag set in `tsconfig/base.json` (`strict` plus `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, `noUncheckedSideEffectImports`, `verbatimModuleSyntax`). Python: `[tool.ty.rules]` in the root `pyproject.toml` promotes every rule ty ships at default level "warn" to "error".

## Test tiers

Two tiers, split by a pytest marker.

**Fast (the default).** `pnpm test` runs Vitest and pytest with no services — hermetic, nothing to start. The pytest side deselects `-m integration` through `addopts`, so the tier stays fast by default rather than by anyone remembering a flag.

**Integration.** `pnpm test:integration` runs the tests marked `@pytest.mark.integration` against the real Postgres, Redis, and Garage, with the URLs from `.env.example` in the environment. It lives in `apps/api/tests/integration/` and `packages/core/tests/integration/`. CI runs it in its own `integration` job, which starts the same three services with `docker compose up -d --wait` rather than with service containers — Garage needs its mounted config, and a service container starts before the checkout that would provide it.

The integration tier owns its state, because the stack is long-lived and shared: no test may assume a fresh one, and two runs never collide. The api tier's session fixture creates a database of its own on the running Postgres, migrates it to head, and drops it at the end; the core tier's store tests either read without writing or write under a key of their own and remove it afterwards.
