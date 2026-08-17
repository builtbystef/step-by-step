---
id: h9gene
title: 'Prefactor: Postgres in compose, a request-scoped DB session, and the integration test tier'
state: todo
priority: high
parent: ufnuvx
created: 2026-08-14T05:44:51Z
updated: 2026-08-17T04:14:02Z
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
