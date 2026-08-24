# Architecture

The modules of this system, and the seams between them. Update this file when the shape changes. Audits compare it with reality.

## Layout

A two-language monorepo, scaffolded from the user's `alloy` template (issue `ymz3md` records the interview that chose it). pnpm + Vite+ (`vp`) run the TypeScript side; uv + ruff + ty + pytest run the Python side. Node and Python versions are pinned in `.node-version` and `.python-version`.

```text
├── apps/
│   ├── api/            # FastAPI backend (Python package: step_by_step_api)
│   │   ├── alembic/    # migrations
│   │   └── Dockerfile  # the backend's compose image
│   ├── extension/      # the MV3 recording extension (plain JavaScript)
│   │   └── src/        # the package Chrome loads unpacked, and the zip's contents
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

`apps/extension` has no build step and no Python of its own: it is the files Chrome loads. The pnpm workspace globs give it `vp check` and `vp test`, and its `package.json` carries the one script the fan-out cannot infer — `test:browser`, which is pytest.

The deployment shape (settled in `px25yw`): one docker compose stack — backend, Workers, Postgres, Redis, Garage. `compose.yaml` at the root holds all five; `docker compose up -d` starts them. `pnpm dev` still runs FastAPI and Next.js on the host for day-to-day frontend work, reaching the stack over its published host ports; the containerised backend is what a Worker and the VNC path talk to.

**Host ports are shifted, deliberately.** Postgres publishes on **5433**, Redis on **6380**, and Garage's S3 API on **3910** — not 5432, 6379, and 3900 — because another project on the same machine already holds all three. `POSTGRES_PORT`, `REDIS_PORT`, and `GARAGE_S3_PORT` override them; the backend container takes **8001** (`API_PORT`) so that it and `pnpm dev`'s host backend on 8000 coexist. `.env.example` carries the matching URLs. Inside the network the services answer to their own names on their native ports, and `compose.yaml`'s `x-stack-environment` anchor is the single place that says so.

The Workers publish **nothing**. Their VNC servers must be reachable from the backend over the compose network and from nowhere else, which is also what makes `docker compose up --scale worker=N` work: with no published port there is nothing for a replica to collide with, and each container's `:99` display is its own.

The stack is long-lived shared state: dev and the tests all reach the same containers, so nothing may assume it starts fresh.

Garage is the Artifact store, chosen over MinIO on 2026-08-16 after MinIO archived its community edition; `px25yw` carries the reasoning and `ymz3md` the stack fact. What binds code rather than compose: artifacts are read and written through the **S3 API only**, via boto3 against a configurable endpoint URL, so the store stays swappable. Garage has no object versioning, bucket policies, object lock, or server-side encryption — none are used here, since retention is app-driven and ADR 0003 puts encryption in the application layer.

It runs as a single self-bootstrapping node: `garage server --single-node --default-bucket` writes the one-node layout, the access key, and the bucket on first boot from the `GARAGE_DEFAULT_*` variables, so the stack needs no init sidecar and a cold `docker compose up` needs no manual step. `compose/garage.toml` is the mounted config; the `rpc_secret` and `admin_token` it would otherwise carry arrive as `GARAGE_RPC_SECRET` and `GARAGE_ADMIN_TOKEN` so that no credential sits in a committed file. Two named volumes hold its metadata and its data — without them the store is wiped whenever the container is replaced.

## Seams

### The typed API boundary

`apps/api`'s `build` dumps the FastAPI OpenAPI schema to `apps/api/openapi.json`; `packages/api-client`'s `build` regenerates a typed fetch client from it. Both the schema and the generated client are committed, so a fresh clone typechecks without running Python — and CI's `contract` job regenerates both and fails on any diff. The frontend imports only `@step-by-step/api-client`, never raw fetch paths. New FastAPI routes need an `operation_id`; it becomes the generated function name.

### The dev proxy

In dev the browser only talks to Next.js: `apps/web/next.config.ts` rewrites `/api/*` to `http://localhost:8000` (override with `API_URL`), and `/extension` and `/extension.zip` with it — the install page and the build are the backend's, and a download that only worked in the container would be found by the first person to follow the link. No CORS setup exists, deliberately: the extension reaches the backend from a granted origin, where an extension's fetch is not a cross-origin request at all.

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

Tables are declared in the backend, not in core: `step_by_step_api.accounts.models` holds the accounts tables, `step_by_step_api.workflows.models` the Workflow document, Version, and recording-session tables, `step_by_step_api.extension.models` the connect codes, and `step_by_step_api.secrets.models` the Secret vault; `alembic/env.py` imports all four so that `Base.metadata` knows them before autogenerate compares. Core owns the connection, never the schema.

Migrations run with `pnpm --filter api run migrate` (`alembic upgrade head`). Revisions form one linear history from the empty baseline; each schema slice adds its own revision.

`env.py`'s `include_object` hides one thing from autogenerate: the check constraint a non-native `Enum` column writes, which alembic reflects but does not compare, and would otherwise propose dropping in every revision. The names come from the metadata each run, so a column a model really drops takes its constraint out of the filter and the drop is proposed as it should be; `tests/integration/test_migrations.py` holds both halves.

### The vault's encryption

`step_by_step_api.envelope` is the backend's alone — the one module deliberately kept out of `packages/core`, because the Workers that import core must never hold the master key (ADR 0004). It is envelope encryption per ADR 0003, PyNaCl `SecretBox` on both levels: `seal()` mints a fresh 32-byte data key per record, seals the plaintext under it and the data key under the master key, and returns the two blobs a vault row stores; `open_sealed()` reverses it; `rewrap()` re-seals a data key from one master key to another and leaves the plaintext untouched, reporting a record an earlier pass already moved so a half-finished rotation can be re-run rather than corrupted.

`master_key()` reads `STEPBYSTEP_MASTER_KEY` — base64 of 32 bytes — and is the only thing in the module that touches the environment; every other function takes the key it works with, which is what makes rotation a two-key call rather than a global swap. The backend's **lifespan calls it at startup**, so a missing, malformed, or wrong-length key stops the process while an operator is watching rather than failing on the first vault write. In `compose.yaml` the variable sits on the `api` service alone, outside the `x-stack-environment` anchor the Workers share.

### Secrets

`step_by_step_api.secrets` owns the Organization's Secret vault. `models.py` stores only each value's envelope-encrypted value and data key, with names unique inside one Organization; `secret_overrides` adds one identically sealed Personal Override per member and cascades with either the Secret or the user. `routes.py` is the signed-in, active-Organization HTTP surface: every id lookup includes the active Organization, reveals decrypt only the selected row, and list joins only the caller's own override marker. Deleting an Organization cascades through Secrets, and deleting a Secret cascades through all of its overrides.

The Settings Secrets client consumes only the generated API client. A revealed org value or Personal Override lives in that row component's memory and is discarded after thirty seconds; create, edit, delete confirmation, and the caller's override controls all invalidate the one vault query.

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

`step_by_step_api.accounts` is who a person is and how they prove it. Email is the sole identity, there are no passwords, and the tenant is the Organization (ADR 0005). Eight modules, and `orgs.py` below is the ninth:

- `models.py` — seven tables. `users` (unique on `lower(email)`, stored as entered), `sessions`, `signin_codes`, `organizations`, `memberships`, `invitations` — six in one migration, including the columns later slices animate, because a column added now costs nothing and a migration written later costs a deployment — and `signin_code_issuance`, which came with the throttling because a count of what one address has been sent is state no column of an outstanding code could hold: the code row is deleted the moment the code is spent, and a limit a successful sign-in reset would be no limit.
- `codes.py` — the Sign-in Code: six digits from the CSPRNG, ten minutes, single-use, one outstanding per address. The table holds a SHA-256 and never the code. That digest is not a defence against guessing a six-digit number offline and is not meant to be: the protections are the lifetime, the single use, and the two caps below. What it buys is that a leaked backup hands nobody a working code.

  The caps are one defence in two halves, because five guesses at a code only means something while codes are scarce. A code dies after **5 wrong guesses** — and dies to the right code as well, or a guesser who spent five tries would be handed the sixth by finally getting it right; the dead row keeps refusing until it expires or the next request replaces it, which is the recovery and is the one thing only the mailbox's owner can ask for. And one address is sent at most **5 codes an hour**, counted in `signin_code_issuance` as a fixed window — a counter and the moment it opened, not a row per request, which would be a table that grew with the spraying it exists to stop. The counting is one `INSERT … ON CONFLICT DO UPDATE`, so two requests at once cannot both read four and both write five.

- `sessions.py` — a 256-bit opaque token in an httpOnly, `SameSite=Lax` cookie (`Secure` following the request's scheme), against a row holding only its SHA-256. Server-side rather than a JWT because signing out, removing a member, and deleting an account all have to end access now, and a token the server does not store cannot be taken back. `CurrentUser` is the dependency that makes a route signed-in-only, and expiry is its work as well: a session dies after 30 **idle** days, so being used is what buys the next thirty, and `last_seen_at` is written at most once an hour — the column measures silence in days, and writing a row per read of every screen would buy no resolution anybody uses. An expired row is deleted where it is found rather than merely refused, which is the whole of the sweeping this table gets. Revocation everywhere is `end_all`, the row deletion behind `POST /api/auth/logout-all`, and it takes the asking session with the rest: the action exists for a browser its owner no longer has.

  The cookie slides with the row: it carries a 30-day lifetime of its own, so a browser told nothing more would drop it 30 days after signing in and leave a live session nobody could reach. It is re-stamped on the same schedule as the touch, through the `Response` FastAPI hands the dependency — which reaches a handler's answer for every handler that answers with a model, and is replaced wholesale by a handler that returns a `Response` of its own. The two that do are `logout` and `logout-all`, and they are taking the cookie away rather than renewing it.

  `signed_in_user` is also the one dependency that commits. Both writes it can make — the slide and the reaping — are the session layer's own bookkeeping rather than the handler's work, and both have to survive an answer the handler then refuses to give.

- `service.py` — signing up and signing in, which are one flow, plus `SIGNUP_MODE`. Verifying returns a verdict rather than raising, so that the route commits what happened — a spent code, a counted wrong guess, a created account — before answering with it.
- `invitations.py` — the offer that makes a team: an address (not an account) is invited into an Organization with a role, the offer stands for 14 days, and accepting it while signed in with that address is what creates the Membership. Two refusals guard it, and both are about the address rather than the string: 409 `already_member` and 409 `already_invited`. Revoked, expired, taken, and never made all answer 404 `invitation_not_found` — an id somebody else holds is not a fact they may confirm by guessing at it.
- `members.py` — the Membership lifecycle after joining: who is in an Organization, the role changes between member and admin, removal, leaving (the same route as removal, asked by the person it is about), and the transfer that is the only way an Organization's one owner changes. Every refusal that protects that owner is one code, `is_owner` — from a caller's side it is one fact, that the Membership is not theirs to end or to rewrite — and the transfer locks both rows before writing either, so two of them cannot leave two owners. A Membership ending ends access at once and nothing else: the gate reads the row on every request, so there is no session to revoke, and the Organization's own work belongs to the Organization rather than to whoever left. Deleting a leaver's Personal Overrides waits for the vault that holds them (`o99b7t`).
- `deletion.py` — leaving, at both levels, and it is complete: an owner ends an Organization behind typing its name, a user ends their own account behind typing its address, and neither has a grace period. What goes with each is the schema's rather than this module's — the ownership cascade runs in two directions and every table joins one of them, so one `DELETE` takes everything that belonged to what it names and no deletion can leave a row pointing at something that is gone. `signin_codes` is the one row belonging to a user that no cascade reaches, because a Sign-in Code is keyed by an address rather than by an account, and it is deleted by hand; the issuance count is deliberately left, since clearing it would make ending an account a way to ask for another five codes. Two refusals, and a screen can act on both: 400 `confirmation_mismatch` for a name or an address that does not match, and 403 `sole_owner` for an account that still owns an Organization — an Organization has exactly one owner, so an owner leaving would leave a team nobody can rename, hand on, or end. The confirmation is read before the Organizations are, so the second refusal only ever reaches somebody who meant it.
- `routes.py` — the HTTP surface, including the unauthenticated `/api/instance`.

Requesting a code answers 202 whether or not the address is anybody: an answer that varied would be a way to ask which addresses are on this instance. The wording of the email varies instead, by what entering the code will do. The issuance limit is the one refusal that route has — 429 `rate_limited` — and it says nothing about the address: it is about how often the caller has asked, and the caller is the one who made the requests being counted. Entering a code refuses in three ways instead, and a client tells them apart by the code alone: 401 `bad_code` for wrong, expired, spent, and never issued together, 429 `code_exhausted` for a code that has taken its guesses, 403 `signup_closed` for a right code on an instance that takes nobody new.

`SIGNUP_MODE` (`open` by default, `invite_only` the other) decides whether verifying a code for an unknown address creates the account. There is no instance settings table and no instance administrator. It is read per request and proven at boot, beside the master key and the mailer.

`orgs.py` is the module every domain route uses, and the one place a role becomes a permission: `ActiveMembership` reads the `X-Organization` header, finds the caller's Membership in what it names, and refuses without one — 400 `organization_required` when the header is absent, 403 `not_a_member` when the caller is not in that Organization or when the id is not a UUID at all (which of those two it was is not a client's business). The header is optional in the OpenAPI schema and required at runtime, deliberately: the frontend's fetch wrapper sets it on every request, so a required parameter would make each generated call site pass what one interceptor already carries — and a missing one has to arrive as this application's error shape rather than as FastAPI's 422.

An Organization's own routes name it in the path instead, and there the gate comes in three widths: `PathMembership` is every member's (reading who else is here, and leaving), `ManagingMembership` adds 403 `not_an_admin` for the controls that manage a team, and `OwningMembership` adds 403 `not_the_owner` for the acts an Organization has exactly one person for. A member is told they are not an admin rather than that they are not a member: they are in this Organization, and hiding that from them would hide a fact they already hold. `orgs.create` is the one way an Organization comes into being — the signup's auto-created one and every later one both go through it, so an Organization without an owner is not expressible.

An Invitation is also the signup permit. `SIGNUP_MODE=invite_only` turns `may_sign_up` from "anyone" into "anyone invited", one rule that both the sign-in email's wording and the verification read: the mail reaches the mailbox and nobody else, so it can say the code will create an account where the 202 must not. An account created that way starts with no Organization of its own — it came to join one that already exists, and an empty Organization named after the address is one nobody asked for.

### Workflows

`step_by_step_api.workflows` is the document store the recorder writes and the editor edits, and the immutable Versions publishing mints from it. A Workflow belongs to exactly one Organization (ADR 0005), carries its default step timeout and its takeover timeout as explicit columns, and holds its Steps nowhere near a table:

- `models.py` — `workflows`, `workflow_drafts`, `workflow_versions`, and `recording_sessions`. The Draft is a row of its own rather than a column on the Workflow, because a Version stores the same document shape and a list screen must read a name without dragging a two-hundred-Step document behind it. The document is one JSONB value, so a per-type payload change is a code change and never a migration. A Version is keyed by the pair `(workflow_id, number)` — the number is what a user says about their own Workflow, not a global sequence — and nothing writes to the table after the insert. A recording session holds only a token hash, its one-user/one-Draft scope, expiry, and the newest full checkpoint buffer.
- `document.py` — the document contract, and the only place that knows what a Step is. The eight Step types are a Pydantic union discriminated by `type`, so the generated TypeScript client hands the editor a tagged union rather than an untyped blob. Two rules read the document as a whole and live in `validated()`: no repeated Step id, and no `{{name}}` that `variables` does not declare — which is how deleting a Variable a Step still uses is refused at the seam rather than in a screen. `{{name}}` is interpolated in a navigate URL and a type value and nowhere else; a `{{` in any other value is text. It also holds the two derivations publishing needs: `diff()` keys on Step ids, so a Step that only moved is neither added, changed, nor removed, and `draft_state()` compares the two stored documents whole — never-published, unpublished-changes, in-sync. `standing()` is that last rule with the comparison taken out of it, so the list can make the comparison in the database and still read the three words from here.
- `catalog.py` — everything around the document: the list a user lands on, and reading, renaming, duplicating, and deleting one Workflow. Its query joins the Draft and the newest Version for two facts and no documents — when the document was last touched, and whether it still matches what is published — so a page of rows travels as a page of names. The three sorts are a closed set because each is a keyset the cursor is built on, and the cursor is a base64 `(sort, key, id)` that is refused in any order but its own. `GET /api/workflows/{id}` answers the same row the list would have drawn, which is how the Workflow page's header survives a reload.
- `routes.py` — create a Workflow (name only; the rest of the CRUD contract is the app shell's), read the Draft, replace the Draft, publish, list and read Versions, restore one into the Draft, and compare the Draft against the latest Version. Its `DocumentRoute` turns FastAPI's own 422 into this application's `{code, message}`, so that a client of the Draft routes reads one dialect for every refusal: `unknown_step_type`, `malformed_payload`, `duplicate_variable_name`, `duplicate_step_id`, `undeclared_variable`.
- `recording.py` — mint and re-mint one-hour recording capabilities, retain the newest full-buffer checkpoint by sequence, and finalize either by replacing the Draft or by patching the one target a Re-pick session names. Session traffic carries the opaque token alone; the database stores its digest, user and Draft scope, and checkpoint so neither a closed app tab nor an expired token loses recorded Steps.

**This document is the one part of the API that is camelCase.** `timeoutMs`, `outputName`, `subSelector`, `successCheck` — the names the spec pinned, because the recorder and the editor both write this document in JavaScript. Everything else on the wire stays snake_case. A field nobody set is left out rather than serialized as `null`: absence is what optional means here, and a Draft must read back as the document that was saved.

**Activity is the later of two stamps.** A Workflow's `updated_at` moves on a rename and its Draft's on an edit, and `last_activity_at` is `GREATEST` of the pair — both are things that happened to the Workflow. Once Runs exist it becomes the latest Run's time, falling back to that pair.

**A draft state is derived and never stored.** A stored flag would be a second truth, set by each of the three paths that write a Draft — the editor's save, the recorder's finalize, a restore — and the one that forgot would leave a Workflow claiming to be in sync with a Version it no longer matches. One route answers both readers of that derivation: the publish modal reads the three lists, and the Draft chip in the editor header and the Workflows list reads the state.

Publishing copies the Draft's stored JSONB across as it is rather than re-serializing it through the models, so what a Run reads weeks later is byte-for-byte what the editor was looking at. It takes the Draft row's lock first: two publishes that read the same count would otherwise mint the same number, and the composite key would turn the loser's work into a database error. A restore is an edit of the Draft and mints nothing, and the document it brings back is not revalidated — a Version is executable forever, which refusing one against a rule that has since grown stricter would make it exactly not.

Another Organization's Workflow answers 404 and never 403. A refusal that admitted the id exists would let anyone map another tenant's Workflows one guess at a time.

### Runs and dispatch

`step_by_step_api.runs` owns the persisted execution record and the first four user-facing Run routes. `models.py` holds `runs`, `step_results`, `run_control_intervals`, and `run_log_lines`, including the closed lifecycle and failure-reason sets. Runs belong to an Organization, point to an immutable Workflow Version except for test Runs, and carry only non-secret Variable values; a test Run instead carries the Draft snapshot it will execute. The partial `(org_id, takeover_deadline_at)` index over non-terminal Runs is the attention query's ground.

`routes.py` starts manual and test Runs, lists them by a newest-first `(queued_at, id)` keyset, reconstructs detail from the Run, ordered Step Results, and control intervals, and cancels queued Runs immediately. Every lookup passes through the active-Organization Membership gate, so an id from another Organization is 404. Starting commits the queued row to Postgres first, then performs one `LPUSH` of its id to `step_by_step_core.bus.DISPATCH_LIST`; Redis is a dispatch hint, never the record of whether the Run exists. Active cancellation, Worker claims, Artifact rows, and Batch rows arrive in their owning execution slices, so detail returns empty Artifacts and no Batch row until those stores exist.

### The extension, and how it reaches an instance

`apps/extension` is the recorder: plain MV3 JavaScript, no framework and no build step, so the directory Chrome loads unpacked is also the artifact the backend serves. The manifest pins a `key` — the extension id then follows the package rather than the directory it was installed from, which is what an enterprise-policy install and any later Web Store continuity need — declares `minimum_chrome_version: "118"` (from 118 an attached `chrome.debugger` session resets the service worker's idle timer), and asks for broad host access as an **optional** permission only. An install grants `storage` and `scripting` and reaches no site until somebody names one.

**Distribution is unpacked (n52g83).** There is no Web Store listing and no self-hosted `.crx` with an update feed, because an off-store `.crx` installs on Linux alone. `step_by_step_api.extension.package` serves the paired build instead: `GET /extension.zip` zips the directory with the manifest at its root, and `GET /extension` is the install page beside it — unzip, `chrome://extensions`, Developer mode, Load unpacked. Both are unauthenticated, because somebody who cannot sign in yet still has to be able to install the thing that records, and both are outside `/api` and outside the generated client: they are documents a browser is pointed at. A Windows or macOS fleet can force-install the same package through enterprise policy; nothing is built for that, and the install page says so in one sentence. The image carries the package at `EXTENSION_DIR`, and an instance without one answers 503 `extension_unavailable` on those three routes rather than failing at boot — what is missing is the download, not the instance.

`GET /api/extension/version` reports `{current, minimum_supported}`, unauthenticated. `current` is the served build's own manifest version, so an instance cannot claim a build it does not have; `minimum_supported` lives beside it in `package.py` because two readers need the same number — the app's out-of-date banner, and the refusal a recording session gives an extension that is too old.

**The extension opens the channel, never the app.** `externally_connectable.matches` cannot express an arbitrary self-hosted origin — wildcards over effective TLDs are rejected — so one shared build cannot be messaged by an app whose origin is unknown at build time. Connecting is therefore the extension's move, once per instance:

- The popup is the only place a permission can be asked for, because Chrome grants an optional host permission from a user gesture alone. `chrome.permissions.request` is called from the click itself, before anything is awaited.
- **The grant is what finishes the connect, not the popup.** Chrome's permission dialog is a window that takes focus, and a popup that loses focus is closed — so on most desktops the popup is gone before the answer arrives, and code waiting on that promise never runs. The click therefore tells the worker what it is about to do _before_ it asks, and `chrome.permissions.onAdded` finishes it. When the popup does survive it asks too; whichever arrives first takes the announcement and the other joins the same promise, so one grant opens one tab and spends one code.
- On the grant, `service-worker.js` mints a 256-bit nonce, opens `<origin>/connect?nonce=…`, and injects `pageBridge` into that tab. The bridge is a function rather than a file: a content script cannot import a module, and the protocol's names would otherwise be written twice with nothing to keep them the same.
- The page posts the nonce back into its own window; the bridge forwards it only if it came from that window at that origin; and the worker acts on it only if the sender is this extension, in the top frame of the tab the attempt opened, at the attempt's origin, carrying the attempt's nonce. A refusal names its reason to the worker's log and never to the tab.
- The fallback, when that handshake does not happen: the app's connect screen shows a one-time code (`POST /api/extension/connect-codes`, authenticated, single-use, ten minutes), and the popup spends it (`POST /api/extension/connect`, unauthenticated, 401 `bad_code`). A spent code proves exactly what the handshake proves — a live instance whose signed-in user authorized this pairing — and nothing else, which is why the answer is an empty body. The code path asks for the same origin from its own click, because a fetch to an origin Chrome has not granted is a cross-origin request the backend deliberately does not answer.

The service worker is a restartable coordinator: the connection lives in `storage.local`, the attempt in `storage.session`, every listener is registered at the top level, and nothing is held in a variable that has to survive Chrome's 30-second idle kill.

On the app's side, `apps/web/app/connect/` is the page the extension opens and `apps/web/lib/extension-protocol.ts` is the app's half of the message names. The extension has no build step and nothing importable from a Next app, so `extension-protocol.test.ts` reads `apps/extension/src/lib/handshake.js` and asserts the names are the same in both — a rename on one side that missed the other would break connecting with nothing to show for it.

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

`selectors.py` is the replay half of the selector contract — `resolve(page, target, deadline)`, the module the executor will call for every targeting Step. It walks a Target's candidates in recorded order and takes the first that matches **exactly one** element: zero matches and several matches are the same answer, so nothing here uses `.first()`, `.nth()`, or `or_()`, and a page that grew a second Save button fails rather than guesses. A failed walk is repeated until the deadline — the Step's timeout _is_ the retry budget, and there is no separate retry counter — and each walk is announced through `on_walk`, which is where a Run checks whether it has been cancelled or paused, the one moment in a resolution when nothing has been clicked yet. What comes back carries the matching candidate's rank, which is the Selector Drift signal a Step Result records. The Target it takes is read from the stored Step document with `Target.from_document`; the Worker cannot import the backend's Pydantic contract, and `packages/core` holds no document models yet (`xkfmw8`).

At startup the Worker proves it can reach everything a Run needs — Redis, Postgres, its display, its VNC server, and the Artifact store, the last by a real write-read-delete round trip — logs what each check found, and refuses to start if any failed. Every check runs even after one fails, so one boot shows an operator every problem rather than one problem per boot. Then it idles: there is no dispatch and no executor yet.

The VNC server takes no password today. It is unreachable from anywhere but the compose network, and the view-only and control credentials the backend proxy authenticates with arrive with `5yu03g`, which owns the proxy that uses them.

### The frontend's visual language

`apps/web` is Tailwind CSS 4 with shadcn/ui generated against Base UI (`components.json` style `base-nova`), and TanStack Query for server state. The vocabulary lives in four places, and a screen inherits it rather than inventing one:

- `app/globals.css` — the only file that may name a colour. It defines the surfaces (`--bg`, `--panel`, `--ink`, `--mut`, `--line`) and the five-hue semantic ramp (`--accent` the machine is acting, `--wait` a human is needed, `--human` a secret, `--ok` succeeded, `--bad` failed), maps them onto shadcn's own token names so the generated components speak this palette and no second one, and sets the type scale to exactly six sizes. Spacing and radius are Tailwind's defaults untouched. There is no dark mode: the `dark:` variant is rebound to a class the app never sets, so a viewer's OS preference cannot half-apply a palette that does not exist.
- `components/ui/` — shadcn's, generated by its CLI and not hand-edited. `Sidebar` arrived with the shell and brought its own dependencies (`sheet`, `tooltip`, `separator`, `skeleton`, `hooks/use-mobile.ts`) and its own token vocabulary, which `globals.css` maps onto the palette rather than giving values of its own: the shell is a panel beside the work, and its highlight is "interactive", which is the accent.
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

Every generated call goes through the package's one `client`, which `src/index.ts` re-exports for exactly that reason: it is the seam the app configures once. Four modules sit on it.

- `lib/gate.ts` — the route gate. `resolveGate(me, activeOrgRole, pathname)` answers `render` or `redirect`, and it is pure: no router, no DOM, no fetch, so the whole guard is a table that `lib/gate.test.ts` reads back. `landingAfterSignIn(next)` is the other half — `next` arrives in a URL anyone can write, so it is honored only when it is a path of this app (one leading slash, not an auth route) and otherwise falls back to `HOME_PATH`.
- `lib/api.ts` — the global fetch wrapper, and three rules installed separately on the shared client. `installOrganizationHeader(active)` stamps `X-Organization` on the way out, calling `active` per request so that switching re-scopes the very next call. `installUnauthorizedRedirect(navigate)` turns a 401 — a visitor with no session, which is a question the gate already answers — into the redirect the gate names, and the sign-in screen, where `GET /api/auth/me` answers 401 by design, is left alone because the gate says `render` there. `installMembershipLapsed(onLapsed)` reads a `403 not_a_member` from a clone of the answer (the screen still needs the original) and gives the Organization choice up. `app/providers.tsx` installs all three once, empties the query cache before the 401 redirect so a stale identity cannot bounce the visitor back, and invalidates everything after a lapse so a tab open across a removal recovers without a reload.
- `lib/active-org.ts` — which Organization the app is acting in. `activeOrganization(me, remembered)` resolves it — the remembered one when the identity still carries that Membership, the first otherwise — so a Membership that ended cannot keep scoping the app. `chooseOrganization` writes the choice to `localStorage` and tells its watchers, which is how the switcher re-scopes every screen at once; the wrapper reads it back through the same module, deriving the header from the cached identity rather than from a third copy.
- `lib/identity.ts` — who the visitor is, under one query key, so the shell and every consumer share one `GET /api/auth/me`. `signOutAndLeave` ends the session, empties the cache, and lands on sign-in with nothing carried.

### The shell

`app/(shell)/` is the route group every signed-in screen renders inside; `/signin` is the one route outside it. `shell.tsx` resolves the identity once and asks the gate before any child renders, so a signed-out visitor meets a single redirect rather than a sidebar whose nav answers 401. There is no top bar and no dashboard: the page title is the first thing in the content column, under the attention band's slot.

- `nav.ts` and `settings/sections.ts` hold the decisions — what the nav offers and in what order, and which sections a role is offered. Both are read back without a DOM, and `sections.test.ts` checks its answers against `resolveGate`, so the nav and the guard cannot disagree about a section.
- `slots.tsx` is the shell's deferred surfaces: the attention band and the Runs count badge remain for `fkgat7`; the extension connection pill is now live. `ExtensionConnectionProvider` owns one version request and one 1500 ms page probe for the whole shell, re-probes on focus, and supplies the pill, Settings, first-run panel, and editor through context. The connected extension injects its bridge into every page of its instance, where a probe receives the build version; silence deliberately merges not-installed with pointed-elsewhere.
- The sidebar is shadcn's `Sidebar` at `collapsible="icon"`, 216px wide with a 60px rail, and its `open` follows a `(max-width: 1024px)` media query alone — there is no toggle, because a rail the window width explains needs no explaining. Its `--sidebar-*` tokens are mapped onto the palette in `globals.css` rather than given values of their own.
- Settings is a section nav beside one panel, and it is where the accounts slices' screens now live: `settings/account/`, `settings/organization/` (General), `settings/organization/members/`, and `settings/organization/invitations/`. The Organization sections act on the active Organization rather than iterating every Membership. `settings/secrets/`, `settings/logins/`, and `settings/extension/` render placeholder panels until their own specs land.
- `workflows/` is the list the app opens on and the Workflow page beneath it. The decisions are pulled out of the JSX and read back without a DOM: `list.ts` (the page size is the forty-row threshold, so one page decides whether the search box and the sort control render), `actions.ts` (the one list of what can be done to a Workflow, which the row's hover menu and the header's overflow both render), `draft-state.ts` (the badge's word and hue, and the one sentence that refuses a Workflow with no Version), `messages.ts` (a refusal by its `code`, and what the delete dialog names), and `[id]/tabs.ts` (the four tabs as the four addresses they are). A dialog is shadcn's `Dialog`, added with this slice.
- `workflows/[id]/editor/` is the Draft as a card list. The document is edited whole and saved whole, because the Draft API replaces it whole: the screen holds one edited copy, every tool hands back the next one, and the footer sends it — nothing saves as you type. Its decisions are read back without a DOM too: `steps.ts` (what each of the eight types is called, where a Step keeps its targets, and the three types a person can add by hand — the ones that point at no element), `edits.ts` (reorder, delete, add, replace, none of which rewrites a Step id), `summary.ts` (the Step as a sentence, in parts, so a Variable draws as a pill and the element as a token), `badges.ts` (the right-hand column, and the health of a target: unsupported is the recorder's own flag, fragile is a candidate list that offers nothing but CSS), and `messages.ts` (a refused save, where the backend's message is kept rather than dropped, because it is the only thing that says which Step of a hundred is wrong).
- Variables are edited in the same document as the Steps, from a drawer over the card list (`variables-drawer.tsx`), and `variables.ts` holds what that costs: which Steps stand on each declaration, why a name cannot be declared, and why one cannot be deleted — the document store's own two rules, said before the save rather than after it, because a refusal about a whole document cannot name the three Steps in the way. A rename is one edit that rewrites the declaration and every value reaching for it, since either half alone is the document the store refuses; the same is true of making a Variable out of a literal a recording captured, which is what `value-field.tsx` offers beside a navigate URL and a type value. Secret is a flag on the declaration and never a shape of the syntax: it is what a pill is drawn from, and what masking will key off later.
- The version surface sits in the Workflow header, over the same editor: `[id]/versions.ts` holds which document is being shown and what restoring one costs, and `[id]/publish.ts` arranges the backend's one comparison into what the publish modal states — the number about to be minted, the three lists of Steps, and a sentence for the cases a step diff cannot show (a Draft in sync, an edit that only moved the order or the Variables, a Workflow with no Steps at all). Which Version is open lives in the address (`?version=N`) rather than in state, for the reason the tabs are segments: a Version somebody is reading is a place. A Version opens read-only through disabled `fieldset`s around the step form and the Variables drawer, so immutability holds even where a later slice forgets a flag, and the tools that reorder, delete, and add are absent rather than dead. Publishing and restoring both invalidate the Workflow's own key, which is where the Draft chip is drawn from.
- The pending-invitation banner is the shell's (`pending-invitations.tsx`), because an Invitation is the one thing a person can be offered without asking for it. Sign out is in the sidebar's user menu, beside the Organization switcher, and not in Settings: leaving is not a setting.

### Strictness

Both typecheckers run at full strict, set at scaffold time. TypeScript: the flag set in `tsconfig/base.json` (`strict` plus `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, `noUncheckedSideEffectImports`, `verbatimModuleSyntax`). Python: `[tool.ty.rules]` in the root `pyproject.toml` promotes every rule ty ships at default level "warn" to "error".

## Test tiers

Three tiers, split by pytest markers.

**Fast (the default).** `pnpm test` runs Vitest and pytest with no services — hermetic, nothing to start. The pytest side deselects `-m 'not integration and not browser'` through `addopts`, so the tier stays fast by default rather than by anyone remembering a flag.

**Integration.** `pnpm test:integration` runs the tests marked `@pytest.mark.integration` against the real Postgres, Redis, and Garage, with the URLs from `.env.example` in the environment. It lives in `apps/api/tests/integration/` and `packages/core/tests/integration/`. CI runs it in its own `integration` job, which starts the same three services with `docker compose up -d --wait` rather than with service containers — Garage needs its mounted config, and a service container starts before the checkout that would provide it.

**Browser.** `pnpm test:browser` runs the tests marked `@pytest.mark.browser` — the selector resolution module against local fixture pages, the extension's connect handshake, and later the recorder's capture pipeline. They need a Playwright browser and nothing else: no Postgres, no Redis, no compose. It is a tier of its own because the browser binary does not arrive with `uv sync` — `uv run playwright install chromium` puts it there, and CI's `browser` job does the same before running `pytest -m browser`. It lives in `apps/worker/tests/browser/` and `apps/extension/tests/browser/`, where a session-scoped Chromium and a loopback HTTP server over `pages/` are the whole harness — the extension's copy launching a persistent context with the package loaded unpacked, because an extension has nowhere to live in an incognito one.

One thing that tier cannot reach: the permission grant is a native Chrome dialog raised from a click in the extension's popup, and no automation drives it. What the harness proves is that the package loads under its pinned id and that the handshake is refused unless the tab, the origin, and the nonce are all the attempt's; the grant itself, and the connect flow that follows it, are checked by hand in a real browser.

The integration tier owns its state, because the stack is long-lived and shared: no test may assume a fresh one, and two runs never collide. The api tier's session fixture creates a database of its own on the running Postgres, migrates it to head, and drops it at the end; the core tier's store tests either read without writing or write under a key of their own and remove it afterwards.
