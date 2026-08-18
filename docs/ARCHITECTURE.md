# Architecture

The modules of this system, and the seams between them. Update this file when the shape changes. Audits compare it with reality.

## Layout

A two-language monorepo, scaffolded from the user's `alloy` template (issue `ymz3md` records the interview that chose it). pnpm + Vite+ (`vp`) run the TypeScript side; uv + ruff + ty + pytest run the Python side. Node and Python versions are pinned in `.node-version` and `.python-version`.

```text
├── apps/
│   ├── api/            # FastAPI backend (Python package: step_by_step_api)
│   │   └── alembic/    # migration scaffold; no migrations yet
│   └── web/            # Next.js frontend
├── packages/
│   └── api-client/     # @step-by-step/api-client — generated from the OpenAPI schema
├── tsconfig/           # shared TypeScript presets (base/node/browser/library)
├── pnpm-workspace.yaml # TS workspace + supply-chain policy
└── pyproject.toml      # uv workspace + ruff/ty/pytest config
```

Two packages are decided but not yet built; each lands with the first slice that needs it:

- `apps/worker` — the Worker (see the glossary): its own uv workspace member, depending on the `step-by-step-api` package for shared models. If that dependency gets awkward, the escape hatch is extracting a shared Python lib into `packages/`.
- `apps/extension` — the MV3 recording extension. The workspace globs and `vp check`/`vp test` cover it the moment it exists.

The deployment shape (settled in `px25yw`): one docker compose stack — backend, Workers, Postgres, Redis, Garage. `compose.yaml` at the root holds it; Postgres is in it today, and Redis, Garage, the backend, and the Workers join with the slices that need them. `docker compose up -d` starts it. The application processes still run on the host — `pnpm dev` runs FastAPI and Next.js directly and they reach the stack over published host ports.

Postgres publishes on host port **5433** by default, not 5432, so the stack does not collide with another project's Postgres on the same machine; `POSTGRES_PORT` overrides it, as `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` override the rest. `.env.example` carries the matching `DATABASE_URL`. The stack is long-lived shared state: dev, the tests, and any sandboxed agent loop all reach the same containers, so nothing may assume it starts fresh.

Garage is the Artifact store, chosen over MinIO on 2026-08-16 after MinIO archived its community edition; `px25yw` carries the reasoning and `ymz3md` the stack fact. What binds code rather than compose: artifacts are read and written through the **S3 API only**, via boto3 against a configurable endpoint URL, so the store stays swappable. Garage has no object versioning, bucket policies, object lock, or server-side encryption — none are used here, since retention is app-driven and ADR 0003 puts encryption in the application layer.

## Seams

### The typed API boundary

`apps/api`'s `build` dumps the FastAPI OpenAPI schema to `apps/api/openapi.json`; `packages/api-client`'s `build` regenerates a typed fetch client from it. Both the schema and the generated client are committed, so a fresh clone typechecks without running Python — and CI's `contract` job regenerates both and fails on any diff. The frontend imports only `@step-by-step/api-client`, never raw fetch paths. New FastAPI routes need an `operation_id`; it becomes the generated function name.

### The dev proxy

In dev the browser only talks to Next.js: `apps/web/next.config.ts` rewrites `/api/*` to `http://localhost:8000` (override with `API_URL`). No CORS setup exists, deliberately.

### The database

SQLAlchemy 2 + Alembic, on psycopg 3 (`postgresql+psycopg://`). The connection URL comes only from the `DATABASE_URL` environment variable — `apps/api/alembic/env.py` sets it, `alembic.ini` carries no URL, and `step_by_step_api.db` reads it too. Nothing defaults it in code, so a missing variable is a loud failure rather than a silent connection to the wrong database.

`step_by_step_api.db` is the seam:

- `Base` — the declarative base every table inherits; `alembic/env.py` autogenerates from its metadata.
- `get_engine()` — the process-wide engine, built on first use rather than at import, so the no-services tier and anything that merely imports the app need no database.
- `SessionDep` — the annotated dependency a route handler declares to receive its request's session. The session opens when the request starts and closes when it ends, rolling back whatever the handler did not commit. Handlers commit for themselves.

Migrations run with `pnpm --filter api run migrate` (`alembic upgrade head`). One revision exists — an empty baseline that gives the runner a head to reach; the accounts slice writes the first tables.

### Strictness

Both typecheckers run at full strict, set at scaffold time. TypeScript: the flag set in `tsconfig/base.json` (`strict` plus `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, `noUncheckedSideEffectImports`, `verbatimModuleSyntax`). Python: `[tool.ty.rules]` in the root `pyproject.toml` promotes every rule ty ships at default level "warn" to "error".

## Test tiers

Two tiers, split by a pytest marker.

**Fast (the default).** `pnpm test` runs Vitest and pytest with no services — hermetic, nothing to start. The pytest side deselects `-m integration` through `addopts`, so the tier stays fast by default rather than by anyone remembering a flag.

**Integration.** `pnpm test:integration` runs the tests marked `@pytest.mark.integration` against the real Postgres, with `DATABASE_URL` in the environment. It lives in `apps/api/tests/integration/`. CI runs it in its own `integration` job against a Postgres service container.

The integration tier owns its state: its session fixture creates a database of its own on the running Postgres, migrates it to head, and drops it at the end. That is what makes it safe against a long-lived shared stack — no test may assume a fresh one, and two runs never collide.
