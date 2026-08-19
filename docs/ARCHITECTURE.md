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

Tables are declared in the backend, not in core: `step_by_step_api.accounts.models` holds the six accounts tables and `step_by_step_api.workflows.models` the three Workflow tables, and `alembic/env.py` imports both so that `Base.metadata` knows them before autogenerate compares. Core owns the connection, never the schema.

Migrations run with `pnpm --filter api run migrate` (`alembic upgrade head`). Four revisions exist: the empty baseline that gives the runner a head to reach, the accounts schema, the Workflow document store, and its Versions.

`env.py`'s `include_object` hides one thing from autogenerate: the check constraint a non-native `Enum` column writes, which alembic reflects but does not compare, and would otherwise propose dropping in every revision. The names come from the metadata each run, so a column a model really drops takes its constraint out of the filter and the drop is proposed as it should be; `tests/integration/test_migrations.py` holds both halves.

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

The console adapter's message is a log record, and it reaches an operator only
because **`step_by_step_api.logs` configures application logging** — one
handler on the root logger, on stdout — from the lifespan, ahead of the gates.
That is the single place: uvicorn gives its own `uvicorn*` loggers a handler
and the root none, so before this the Sign-in Code was written to a logger with
nothing attached and dropped (`95v5fm`). uvicorn's loggers do not propagate to
the root, so its access and error records are neither silenced nor doubled, and
every other module does nothing but take its logger and write to it. The Worker
configures its own, in `step_by_step_worker.main`, since it is another process.

The adapter is built once and **at startup**, from the lifespan beside the
master key: a mailer whose configuration is missing stops the boot with the
variable's name, rather than surfacing on the first person's sign-in — and the
Sign-in Code is the only way into an instance. The variables sit on the `api`
service alone in `compose.yaml`, outside the anchor the Workers share, because
the backend sends every email and a Worker sends none.

A failed send raises whatever the adapter's own library raises. v1 has no
caller that catches one, so nothing is wrapped to make them look alike.

### Accounts

`step_by_step_api.accounts` is who a person is and how they prove it. Email is the sole identity, there are no passwords, and the tenant is the Organization (ADR 0005). Six modules:

- `models.py` — the six tables. `users` (unique on `lower(email)`, stored as entered), `sessions`, `signin_codes`, `organizations`, `memberships`, `invitations`. All six landed in one migration, including the columns later slices animate — the wrong-guess counter and the Invitation expiry — because a column added now costs nothing and a migration written later costs a deployment.
- `codes.py` — the Sign-in Code: six digits from the CSPRNG, ten minutes, single-use, one outstanding per address. The table holds a SHA-256 and never the code. That digest is not a defence against guessing a six-digit number offline and is not meant to be: the protections are the lifetime, the single use, and the attempt cap. What it buys is that a leaked backup hands nobody a working code.
- `sessions.py` — a 256-bit opaque token in an httpOnly, `SameSite=Lax` cookie (`Secure` following the request's scheme), against a row holding only its SHA-256. Server-side rather than a JWT because signing out, removing a member, and deleting an account all have to end access now, and a token the server does not store cannot be taken back. `CurrentUser` is the dependency that makes a route signed-in-only.
- `service.py` — signing up and signing in, which are one flow, plus `SIGNUP_MODE`. Verifying returns a verdict rather than raising, so that the route commits what happened — a spent code, a counted wrong guess, a created account — before answering with it.
- `invitations.py` — the offer that makes a team: an address (not an account) is invited into an Organization with a role, the offer stands for 14 days, and accepting it while signed in with that address is what creates the Membership. Two refusals guard it, and both are about the address rather than the string: 409 `already_member` and 409 `already_invited`. Revoked, expired, taken, and never made all answer 404 `invitation_not_found` — an id somebody else holds is not a fact they may confirm by guessing at it.
- `routes.py` — the HTTP surface, including the unauthenticated `/api/instance`.

Requesting a code answers 202 whether or not the address is anybody: an answer that varied would be a way to ask which addresses are on this instance. The wording of the email varies instead, by what entering the code will do.

`SIGNUP_MODE` (`open` by default, `invite_only` the other) decides whether verifying a code for an unknown address creates the account. There is no instance settings table and no instance administrator. It is read per request and proven at boot, beside the master key and the mailer.

`orgs.py` is the seventh module and the one every domain route uses: `ActiveMembership` reads the `X-Organization` header, finds the caller's Membership in what it names, and refuses without one — 400 `organization_required` when the header is absent, 403 `not_a_member` when the caller is not in that Organization or when the id is not a UUID at all (which of those two it was is not a client's business). The header is optional in the OpenAPI schema and required at runtime, deliberately: the frontend's fetch wrapper sets it on every request, so a required parameter would make each generated call site pass what one interceptor already carries — and a missing one has to arrive as this application's error shape rather than as FastAPI's 422.

An Organization's own routes name it in the path instead of in the header, because they are about one Organization rather than acting inside the active one, and there the role matters as well: `ManagingMembership` is the same lookup with a role gate, answering 403 `not_an_admin` to a member. A member is told they are not an admin rather than that they are not a member — they are in this Organization, and hiding what they already know would buy nothing.

An Invitation is also the signup permit. `SIGNUP_MODE=invite_only` turns `may_sign_up` from "anyone" into "anyone invited", one rule that both the sign-in email's wording and the verification read: the mail reaches the mailbox and nobody else, so it can say the code will create an account where the 202 must not. An account created that way starts with no Organization of its own — it came to join one that already exists, and an empty Organization named after the address is one nobody asked for.

### Workflows

`step_by_step_api.workflows` is the document store the recorder writes and the editor edits, and the immutable Versions publishing mints from it. A Workflow belongs to exactly one Organization (ADR 0005), carries its default step timeout and its takeover timeout as explicit columns, and holds its Steps nowhere near a table:

- `models.py` — `workflows`, `workflow_drafts`, and `workflow_versions`. The Draft is a row of its own rather than a column on the Workflow, because a Version stores the same document shape and a list screen must read a name without dragging a two-hundred-Step document behind it. The document is one JSONB value, so a per-type payload change is a code change and never a migration. A Version is keyed by the pair `(workflow_id, number)` — the number is what a user says about their own Workflow, not a global sequence — and nothing writes to the table after the insert.
- `document.py` — the document contract, and the only place that knows what a Step is. The eight Step types are a Pydantic union discriminated by `type`, so the generated TypeScript client hands the editor a tagged union rather than an untyped blob. Two rules read the document as a whole and live in `validated()`: no repeated Step id, and no `{{name}}` that `variables` does not declare — which is how deleting a Variable a Step still uses is refused at the seam rather than in a screen. `{{name}}` is interpolated in a navigate URL and a type value and nowhere else; a `{{` in any other value is text. It also holds the two derivations publishing needs: `diff()` keys on Step ids, so a Step that only moved is neither added, changed, nor removed, and `draft_state()` compares the two stored documents whole — never-published, unpublished-changes, in-sync.
- `routes.py` — create a Workflow (name only; the rest of the CRUD contract is the app shell's), read the Draft, replace the Draft, publish, list and read Versions, restore one into the Draft, and compare the Draft against the latest Version. Its `DocumentRoute` turns FastAPI's own 422 into this application's `{code, message}`, so that a client of the Draft routes reads one dialect for every refusal: `unknown_step_type`, `malformed_payload`, `duplicate_variable_name`, `duplicate_step_id`, `undeclared_variable`.

**This document is the one part of the API that is camelCase.** `timeoutMs`, `outputName`, `subSelector`, `successCheck` — the names the spec pinned, because the recorder and the editor both write this document in JavaScript. Everything else on the wire stays snake_case. A field nobody set is left out rather than serialized as `null`: absence is what optional means here, and a Draft must read back as the document that was saved.

**A draft state is derived and never stored.** A stored flag would be a second truth, set by each of the three paths that write a Draft — the editor's save, the recorder's finalize, a restore — and the one that forgot would leave a Workflow claiming to be in sync with a Version it no longer matches. One route answers both readers of that derivation: the publish modal reads the three lists, and the Draft chip in the editor header and the Workflows list reads the state.

Publishing copies the Draft's stored JSONB across as it is rather than re-serializing it through the models, so what a Run reads weeks later is byte-for-byte what the editor was looking at. It takes the Draft row's lock first: two publishes that read the same count would otherwise mint the same number, and the composite key would turn the loser's work into a database error. A restore is an edit of the Draft and mints nothing, and the document it brings back is not revalidated — a Version is executable forever, which refusing one against a rule that has since grown stricter would make it exactly not.

Another Organization's Workflow answers 404 and never 403. A refusal that admitted the id exists would let anyone map another tenant's Workflows one guess at a time.

### Errors

`step_by_step_api.errors` is the one refusal shape: `{code, message}`, raised as `ApiError` from anywhere in a request. A client decides what to do from `code` and never from prose — the sign-in screen tells a wrong code from a closed instance by that field alone. `errors(401, 403)` on a route is what puts the model in the OpenAPI schema, so the generated client types what the frontend reads.

### The clock

`step_by_step_api.clock` is the one place the current time enters. Sign-in Codes expire, sessions slide, and Invitations run out — three behaviours whose tests would otherwise wait real minutes. Every one of them asks `clock.now()`, so a test moves time by replacing one function.

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

### The frontend's data layer

`apps/web` imports only `@step-by-step/api-client`. The generated functions return `{data, error}` rather than throwing, so a 401 is a value the screen reads and not an exception it has to catch. Cookies ride along because the browser talks to one origin: the Next proxy makes the session cookie same-origin, which is also what makes `SameSite=Lax` the whole CSRF story.

Every generated call goes through the package's one `client`, which `src/index.ts` re-exports for exactly that reason: it is the seam the app configures once. Three modules sit on it.

- `lib/gate.ts` — the route gate. `resolveGate(me, activeOrgRole, pathname)` answers `render` or `redirect`, and it is pure: no router, no DOM, no fetch, so the whole guard is a table that `lib/gate.test.ts` reads back. `landingAfterSignIn(next)` is the other half — `next` arrives in a URL anyone can write, so it is honored only when it is a path of this app (one leading slash, not an auth route) and otherwise falls back to `HOME_PATH`.
- `lib/api.ts` — the global fetch wrapper. `installUnauthorizedRedirect(navigate)` installs one response interceptor on the shared client: a 401 means the visitor has no session, which is a question the gate already answers, so it asks it with the path the visitor is on. A tab left open across a session expiry therefore recovers with a redirect instead of a screenful of errors, and the sign-in screen — where `GET /api/auth/me` answers 401 by design — is left alone because the gate says `render` there. `app/providers.tsx` installs it once for the app and empties the query cache before the redirect, so a stale identity cannot bounce the visitor back. The active Organization's `X-Organization` header belongs in this same interceptor and arrives with the shell.
- `app/invitations/` — the Invitations screen, and the one route that is deliberately temporary. The pending-invitation banner belongs in the shell's chrome and the panel inside Settings → Organization (the path `lib/gate.ts` already reserves); until the shell exists there is nowhere to hang either, and without them an Organization cannot get its second member. `messages.ts` is where its refusals and its "which Organizations may I manage" rule are decided, so both are read back without a DOM.
- `lib/identity.ts` — who the visitor is, under one query key, so the shell and every consumer share one `GET /api/auth/me`. `signOutAndLeave` ends the session, empties the cache, and lands on sign-in with nothing carried.

### Strictness

Both typecheckers run at full strict, set at scaffold time. TypeScript: the flag set in `tsconfig/base.json` (`strict` plus `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, `noUncheckedSideEffectImports`, `verbatimModuleSyntax`). Python: `[tool.ty.rules]` in the root `pyproject.toml` promotes every rule ty ships at default level "warn" to "error".

## Test tiers

Two tiers, split by a pytest marker.

**Fast (the default).** `pnpm test` runs Vitest and pytest with no services — hermetic, nothing to start. The pytest side deselects `-m integration` through `addopts`, so the tier stays fast by default rather than by anyone remembering a flag.

**Integration.** `pnpm test:integration` runs the tests marked `@pytest.mark.integration` against the real Postgres, Redis, and Garage, with the URLs from `.env.example` in the environment. It lives in `apps/api/tests/integration/` and `packages/core/tests/integration/`. CI runs it in its own `integration` job, which starts the same three services with `docker compose up -d --wait` rather than with service containers — Garage needs its mounted config, and a service container starts before the checkout that would provide it.

The integration tier owns its state, because the stack is long-lived and shared: no test may assume a fresh one, and two runs never collide. The api tier's session fixture creates a database of its own on the running Postgres, migrates it to head, and drops it at the end; the core tier's store tests either read without writing or write under a key of their own and remove it afterwards.
