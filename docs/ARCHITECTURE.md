# Architecture

This file describes the current system and the main boundaries between its parts. Update it when those boundaries change.

## Repository layout

Step by Step is a TypeScript and Python monorepo.

```text
apps/
  api/          FastAPI backend and Alembic migrations
  extension/    Chrome MV3 recorder (plain JavaScript)
  web/          Next.js application
  worker/       Playwright Worker
packages/
  api-client/   TypeScript client generated from OpenAPI
  core/         Python code shared by the API and Worker
compose/        Garage configuration
docs/           Architecture, glossary, standards, and ADRs
```

The root pnpm scripts use Vite+ (`vp`) to run commands in every workspace. Python commands run through uv. Tool versions are pinned in `.node-version`, `.python-version`, `package.json`, and `pyproject.toml`.

## Runtime services

`compose.yaml` defines five services:

- **PostgreSQL** is the source of truth.
- **Redis** carries dispatch hints, live events, and control hints.
- **Garage** stores Run Artifacts through its S3 API.
- **API** serves the HTTP API, the extension package, and the VNC proxy.
- **Worker** runs one browser and at most one Run at a time.

The Next.js app normally runs on the host with `pnpm dev`. It proxies `/api`, `/extension`, and `/extension.zip` to FastAPI, so the browser uses one origin and the API needs no CORS setup.

The default host ports are 5433 for PostgreSQL, 6380 for Redis, 3910 for Garage, and 8001 for the containerized API. Host development uses ports 3000 for Next.js and 8000 for FastAPI. Workers publish no ports. Their VNC servers are available only inside the Compose network.

The service data is long-lived. Tests must not assume that PostgreSQL, Redis, or Garage starts empty.

## Main data flow

1. The Chrome extension records semantic Steps and saves them to a Workflow Draft through the API.
2. Publishing copies the Draft into an immutable Version.
3. Starting a Run writes a queued row to PostgreSQL, then pushes its id to Redis.
4. A Worker claims the row with one conditional database update.
5. The Worker runs the Version in a fresh headed Chromium profile.
6. The Worker writes status, Step Results, logs, control intervals, and Artifact rows to PostgreSQL. It writes Artifact files to Garage and publishes live events to Redis.
7. The web app reads durable state through the API and receives new Run or Batch events over server-sent events.

Redis is never the source of truth. A minute loop requeues old queued Runs, fails Workers that stop sending heartbeats, enforces takeover deadlines, fires Schedules, and advances stalled Batches.

## API boundary

FastAPI writes `apps/api/openapi.json`. The `@step-by-step/api-client` build generates the TypeScript client in `packages/api-client`. Both outputs are committed.

The web app imports the generated client instead of writing API paths by hand. Every public route needs an `operation_id`; it becomes the generated function name. CI regenerates the schema and client and fails if the committed files change.

Worker-only routes live under `/internal`. They use `INTERNAL_TOKEN` and are not included in the generated browser client.

API errors use one shape:

```json
{ "code": "machine_readable_code", "message": "Plain-language explanation" }
```

Clients branch on `code`, not on `message`.

## Shared Python boundary

`packages/core` is the small library imported by both the API and Worker:

- `step_by_step_core.db` owns the SQLAlchemy engine and session helpers.
- `step_by_step_core.bus` owns the Redis client and dispatch list name.
- `step_by_step_core.objects` owns the S3 clients and bucket setting.
- `step_by_step_core.document` defines the Workflow document.
- `step_by_step_core.events` defines Run and Batch events and the durable-log helper.

Database models stay in the API package. The Worker does not import them; it uses the shared database session and explicit SQL for its writes.

The encryption module stays in the API package. It must never enter the Worker image.

## Database

SQLAlchemy 2 uses psycopg 3. Alembic owns schema changes. `DATABASE_URL` is required; there is no connection URL in code or `alembic.ini`.

The main model groups are:

- `accounts`: users, sessions, Organizations, Memberships, Invitations, and Sign-in Codes
- `workflows`: Workflows, Drafts, Versions, and recording sessions
- `secrets`: Secrets and Personal Overrides
- `auth_states`: saved browser state and Personal Overrides
- `runs`: Runs, Step Results, logs, control intervals, takeover tickets, Auth State candidates, and Artifacts
- `schedules`: Schedules and skipped Occurrences
- `batches`: Batches and their rows

Every tenant-owned domain object belongs to an Organization, either directly or through its parent. API lookups include that scope. A resource id from another Organization normally returns 404 rather than revealing that it exists.

Migrations form one linear history. Run them with `pnpm --filter api run migrate`.

## Workflow documents

A Workflow has one mutable Draft. A Draft and a Version store one JSONB document containing Variables, Targets, and Steps. Saving replaces the whole Draft. Publishing copies it to the next immutable Version.

The shared Pydantic model defines eight Step types:

- navigate
- click
- type
- select
- download
- extract
- wait
- pause-for-takeover

Workflow documents use camelCase because the extension and editor write them. Other API bodies use snake_case. Optional document fields are omitted instead of being written as `null`.

Step ids remain stable across edits and Versions. They connect a Step to its diff, Step Results, and Selector Drift history. A Draft may not contain duplicate Step ids, duplicate Variable names, or a Variable reference that it does not declare.

A secret Variable stores a Secret id and a cached display name. It never stores the Secret value.

## Runs and Workers

A Run follows this lifecycle:

```text
queued → running ⇄ waiting_for_human → succeeded | failed | cancelled
```

The closed Failure Reason set is defined in `docs/GLOSSARY.md`. Runs are never retried automatically (ADR 0002).

A Worker is a long-lived process with Xvfb, openbox, x11vnc, and headed Chromium. It checks PostgreSQL, Redis, Garage, its display, and VNC before accepting work. Each claimed Run gets a fresh browser profile, which is removed at the end.

The Worker commits each Step Result before starting the next Step. It checks cancellation, pause requests, and the Run timeout at safe points. Waiting for a human does not count toward the automation timeout.

Three channels connect a live Run:

- **PostgreSQL** stores durable state.
- **Redis** carries dispatch, events, and low-latency control hints.
- **Internal HTTP** gives an assigned Worker heartbeats, control state, resolved credentials, and Auth State write-back.

The backend also proxies **VNC** from the Worker to the web app. Single-use tickets decide whether a connection is view-only or may control the browser.

The Worker gets only the plaintext credentials resolved for its assigned Run. The backend keeps `STEPBYSTEP_MASTER_KEY` and performs all decryption (ADR 0004).

Secret values are replaced with `••••` before logs, errors, or trace text are stored or published. Trace capture pauses around secret-using Steps and during takeover. Screenshots are not taken while a person controls the browser.

## Secrets and Auth State

The API uses envelope encryption with PyNaCl `SecretBox` (ADR 0003). Each record has its own data key, and the environment supplies one 32-byte master key. The API validates the key at startup. `rotate-master-key` rewraps data keys without rewriting plaintext values.

A Secret belongs to an Organization. A member may add a Personal Override. A member-started Run uses that member's override first; Scheduled and Batch Runs use only the Organization value.

Auth State stores cookies and web storage by registrable domain. `libpsl` supplies public-suffix rules. The API never returns saved browser-state contents to the settings UI. Recording and successful Runs can write Auth State only with the user's consent.

The Worker never receives the master key and never chooses between Organization and personal values. The API resolves that choice before returning credentials.

## Schedules and Batches

A Schedule stores a cron expression, IANA timezone, enabled flag, optional name, and non-secret Variable values. It always starts the latest published Version. Its state is derived:

- `paused` when disabled
- `needs_values` when required non-secret values are missing
- `active` otherwise

An Occurrence row is written only when no Run was created. The reasons are `overlap`, `missed`, and `missing_values`.

A Batch stores up to 1,000 input rows and runs them in order. Only one Run in a Batch may be active at a time. Row status follows the latest attempt. Missing required values may skip a row. A failed row does not stop later rows. Users may edit eligible rows, skip a waiting row, re-run a failed or skipped row, or cancel the Batch.

## Artifacts and object storage

Garage is accessed only through the S3 API, using boto3. This keeps the storage provider replaceable.

Two endpoints are required:

- `S3_ENDPOINT_URL` is used by application processes to read and write objects.
- `S3_PUBLIC_ENDPOINT` is used to sign download URLs that a user's browser can open.

These values are often the same on a development host and different inside a deployment. S3 path-style addressing is used in both cases.

Artifact retention is controlled by the application. Deleting a Run, Workflow, or Organization also removes its Artifact objects. Artifact files are not covered by the Secret and Auth State encryption described in ADR 0003; production storage must be protected separately.

## Accounts and tenancy

Email is the only identity. Sign-in uses a short-lived, single-use code. Sessions are opaque server-side tokens stored as hashes in PostgreSQL, with a sliding 30-day idle expiry.

The Organization is the tenant (ADR 0005). Roles are owner, admin, and member. An Organization has exactly one owner. Ending a Membership removes that member's Personal Overrides in the Organization but does not remove shared work.

`SIGNUP_MODE` is either `open` or `invite_only`. There is no instance administrator. Invitations both add existing users and allow invited addresses to create an account on an invite-only instance.

The mail seam supports `console`, `smtp`, and `resend`. The API validates the chosen adapter at startup. The console adapter writes Sign-in Codes to the API log for local development.

## Extension

`apps/extension/src` is plain MV3 JavaScript. There is no build step: the same files are loaded unpacked and packaged by the API as `/extension.zip`. `/extension` serves install instructions. The manifest requires Chrome 118 or newer.

The popup wears the app's design system: `popup.css` repeats the tokens and the type scale from `apps/web/app/globals.css`, and a test fails if that copy drifts. The package carries the brand mark as its toolbar icon; the 16-pixel raster drops the cursor from the mark, which is a smudge at that size, and the larger ones keep it.

The extension asks for site access per origin. It does not request access to every site during installation. Connection details and active recording state are kept in Chrome storage so service-worker restarts do not lose them.

A recording session is a short-lived capability for one user and Workflow. The extension checkpoints the full Step buffer after changes. A password value never crosses the content-script boundary; it becomes a secret binding during save. Re-pick uses the same recording channel but replaces the Target for one Step only.

## Web app

`apps/web` uses Next.js, Tailwind CSS 4, shadcn/ui, Base UI, and TanStack Query.

The route gate and active Organization selection live in reusable modules. The generated API client adds `X-Organization` to requests. A 401 clears cached identity and returns the visitor to sign-in. A `not_a_member` response clears the old Organization choice.

The signed-in shell contains Workflows, Runs, Schedules, and Settings. A Workflow has Editor, Runs, Schedules, and Batches tabs. Settings contains account, Organization, members, Invitations, Secrets, saved logins, and extension screens.

Visual rules that reviews enforce are in `docs/CODING_STANDARDS.md`. In particular, colors come from tokens, lifecycle states use `StatusChip`, and shared Run and Schedule lists have one implementation each.

## Test tiers

- `pnpm test` runs fast Vitest and pytest tests. It needs no services or browser.
- `pnpm test:integration` runs tests against PostgreSQL, Redis, and Garage.
- `pnpm test:browser` runs Playwright tests for Worker browser behavior and the extension.

Integration tests create and remove their own database or object keys. Browser tests need `uv run playwright install chromium`. CI runs all three tiers and checks that generated API files are current.
