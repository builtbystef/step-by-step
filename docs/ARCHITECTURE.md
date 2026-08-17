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

The deployment shape (settled in `px25yw`): one docker compose stack — backend, Workers, Postgres, Redis, Garage. The compose file lands with the first slice that needs a running service; until then, `pnpm dev` runs FastAPI and Next.js directly.

Garage is the Artifact store, chosen over MinIO on 2026-08-16 after MinIO archived its community edition; `px25yw` carries the reasoning and `ymz3md` the stack fact. What binds code rather than compose: artifacts are read and written through the **S3 API only**, via boto3 against a configurable endpoint URL, so the store stays swappable. Garage has no object versioning, bucket policies, object lock, or server-side encryption — none are used here, since retention is app-driven and ADR 0003 puts encryption in the application layer.

## Seams

### The typed API boundary

`apps/api`'s `build` dumps the FastAPI OpenAPI schema to `apps/api/openapi.json`; `packages/api-client`'s `build` regenerates a typed fetch client from it. Both the schema and the generated client are committed, so a fresh clone typechecks without running Python — and CI's `contract` job regenerates both and fails on any diff. The frontend imports only `@step-by-step/api-client`, never raw fetch paths. New FastAPI routes need an `operation_id`; it becomes the generated function name.

### The dev proxy

In dev the browser only talks to Next.js: `apps/web/next.config.ts` rewrites `/api/*` to `http://localhost:8000` (override with `API_URL`). No CORS setup exists, deliberately.

### The database

SQLAlchemy 2 + Alembic. The connection URL comes only from the `DATABASE_URL` environment variable (`apps/api/alembic/env.py` sets it; `alembic.ini` carries no URL). No tables and no migrations exist yet — the first slice that needs a table writes the first model and the first migration, and points `target_metadata` at the models' metadata.

### Strictness

Both typecheckers run at full strict, set at scaffold time. TypeScript: the flag set in `tsconfig/base.json` (`strict` plus `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, `noUncheckedSideEffectImports`, `verbatimModuleSyntax`). Python: `[tool.ty.rules]` in the root `pyproject.toml` promotes every rule ty ships at default level "warn" to "error".

## Test tiers

One tier today: `pnpm test` runs Vitest and pytest with no services — fast, hermetic. A marked integration tier (Postgres/Redis via compose) appears with the first test that needs it, separated so the fast tier stays the default.
