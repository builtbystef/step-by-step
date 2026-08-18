---
id: h9gene
title: 'Prefactor: Postgres in compose, a request-scoped DB session, and the integration test tier'
state: done
assignee: claude
priority: high
parent: ufnuvx
created: 2026-08-14T05:44:51Z
updated: 2026-08-18T06:34:17Z
---

## What to build

The rails every accounts slice rides on. One compose command brings up a Postgres for development and tests. The backend owns a database engine whose connection URL comes only from the environment, and route handlers receive a request-scoped database session. Migrations apply cleanly against that Postgres. A marked integration test tier runs against the real database, separated so the existing no-services fast tier stays the default. No domain tables yet — the first models land with the next slice.

## Acceptance criteria

- [ ] A single documented compose command starts Postgres locally; the backend and the migration runner connect to it via the environment-supplied URL and nothing else.
- [ ] Applying migrations against a fresh compose Postgres succeeds and is repeatable (running it twice is a no-op).
- [ ] An integration-marked test tier exists and runs against the real Postgres; an included proof test writes a row and reads it back through the request-scoped session dependency.
- [ ] The default test command still passes with no services running — integration tests are excluded from it and have their own documented invocation (locally and in CI).
- [ ] The architecture doc's test-tiers and deployment sections reflect the new shape.

## Notes

**claude** — 2026-08-17T04:14:02Z

Execution-environment pin (loop operator's decision): this ticket runs as a supervised HOST session, not in the sandbox — its ACs verify docker compose itself, and the sandbox deliberately has no Docker. The compose stack it creates is long-lived shared state (dev, the sandboxed loop, and the verify command all reach it over localhost via host networking), so the integration tier must own its state: a dedicated test database or equivalent per-run isolation, never an assumption of a fresh stack. Document the integration invocation so the operator can add it to LOOP_VERIFY_CMD.

**claude** — 2026-08-18T06:34:17Z

Done. The rails are in place; no domain tables, as the ticket specified.

**What landed**

- `compose.yaml` at the root, `name: step-by-step`, one `postgres` service (postgres:17, named volume, healthcheck). `docker compose up -d` is the documented command. Host port defaults to **5433**, not 5432, because a developer's other project already holds 5432 on the same machine; `POSTGRES_PORT` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` override. `.env.example` carries the matching `DATABASE_URL`.
- `step_by_step_api.db` — `Base` (declarative base), `get_engine()` (lru_cached, built on first use), `get_session()` (one session per request, rolling back what the handler did not commit), and `SessionDep`. The URL is read from `environ["DATABASE_URL"]` with no default anywhere; `alembic.ini` still carries none.
- `alembic/env.py` now points `target_metadata` at `Base.metadata`, and `alembic/versions/14699da4a661_baseline.py` is the empty first revision. `pnpm --filter api run migrate` applies it.
- Integration tier at `apps/api/tests/integration/`, marker `integration`, run with `pnpm test:integration`. CI gained an `integration` job against a Postgres service container.

**Decisions**

- **New production dependency: `psycopg[binary]>=3.2`.** SQLAlchemy 2 needs a driver and the backend's routes are sync, so sync psycopg 3 (`postgresql+psycopg://`) is the fit — asyncpg would force an async stack the app does not have, psycopg2 is the older generation.
- **The engine is lazy, not built at import.** Eager construction would make the no-services fast tier need a database just to import the app. A missing `DATABASE_URL` therefore fails at first use, not at boot; no AC asked for a boot gate here (i1osfd owns that pattern for the master key).
- **A baseline migration with an empty `upgrade()`.** With zero revisions, `alembic upgrade head` is vacuous and the repeatability criterion is untestable. The baseline gives the runner a head to reach, and the accounts slice writes the first tables on top.
- **`Base` lands now rather than with the first model**, so the migration runner is fully wired rather than half-wired behind a TODO.
- **`script.py.mako` modernised** (`str | Sequence[str] | None` instead of `typing.Union`) so generated revisions pass `pnpm check` instead of failing UP rules on arrival.
- **Per-run database isolation**, per the execution-environment note: the session fixture creates `stepbystep_test_<uuid>` on the running Postgres, migrates it to head, and drops it with `WITH (FORCE)`. Nothing assumes a fresh stack.

**Facts a reviewer needs**

- The proof test builds a throwaway FastAPI app with two routes on a `session_probes` table of its own: one request writes through `SessionDep`, a second request reads it back. Mutation-checked — removing the handler's `commit()` makes it fail, so it really proves request scope and durability across requests, not just that a session exists.
- Verified on a fresh stack (`docker compose down -v && up -d`): migrate → applied, migrate again → no-op, `alembic_version` = 14699da4a661. Integration tier run twice in sequence and twice concurrently — all green, and `pg_database` holds no `stepbystep_test%` leftovers afterwards.
- Fast tier verified green with the stack fully down and `DATABASE_URL` unset: 2 passed, 3 deselected.
- `pnpm run ci` passes; `openapi.json` and the generated client are unchanged (no routes added), so the contract job stays clean.
- For the loop operator: the integration invocation is `pnpm test:integration` with `DATABASE_URL` in the environment. It needs the compose stack reachable over localhost, so it belongs in `LOOP_VERIFY_CMD` only for sessions that can reach it.
