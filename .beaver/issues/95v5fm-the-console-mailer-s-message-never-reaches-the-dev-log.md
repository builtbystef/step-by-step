---
id: 95v5fm
title: The console mailer's message never reaches the dev log
state: done
assignee: claude
priority: high
labels:
    - bug
created: 2026-08-18T09:30:38Z
updated: 2026-08-18T09:46:16Z
---

## What is wrong

`ConsoleMailer.send` logs the message with `logging.getLogger(__name__).info(...)`, but `pnpm --filter api dev` runs plain uvicorn, which configures handlers for its own `uvicorn*` loggers and none for the root. Application records at INFO therefore go nowhere: the Sign-in Code is written to a logger with no handler and is dropped.

The effect is that on a default dev instance — `MAILER=console`, the documented "works with no mail service" path — nobody can sign in, because the only way in is a code that is never displayed. Confirmed by hand on 2026-08-18: with `logging.basicConfig(level=INFO)` in front of `uvicorn.run`, the message and its code appear; without it, `grep "mail from"` over the dev log finds nothing.

The seam tests are unaffected — they read the in-process outbox, not the log — which is why this survived `ycn8xm`.

## Acceptance criteria

- [ ] `pnpm --filter api dev` (and the `api` container) show the console mailer's message, including the Sign-in Code, on stdout.
- [ ] The fix configures application logging in one place rather than per call site, and does not silence or duplicate uvicorn's own access and error records.
- [ ] A test proves it at the seam that broke: starting the app the way it is started in production and asserting a mailed message reaches the configured handler.
- [ ] `docs/ARCHITECTURE.md`'s mailer section says where application log records are configured.

## Notes

**claude** — 2026-08-18T09:46:07Z

Fixed in `step_by_step_api.logs`: `configure()` puts one named StreamHandler on the **root** logger, on stdout, with the Worker's format, and sets the root to INFO. The lifespan calls it first, ahead of the master key, the mailer, and the signup mode, so a gate that fails is also said out loud. No call site configures anything.

Decisions:
- The root logger only. uvicorn's `uvicorn` and `uvicorn.access` loggers carry `propagate: false` in its LOGGING_CONFIG, so its access and error records reach its own handlers and never ours — neither silenced nor doubled. Verified as a test, not by reading: the test applies `uvicorn.config.LOGGING_CONFIG` through `dictConfig` first (production order — uvicorn configures logging, then imports the app), then starts the app and asserts each uvicorn record is written exactly once.
- A named handler and an idempotent `configure()`, rather than `logging.basicConfig`. `basicConfig` is a no-op whenever the root already has a handler — which it does under pytest — so it could not be tested at this seam. The name is also what makes a second start (`--reload`, and every test that starts the app) leave the first one's handler alone.
- No `LOG_LEVEL` variable: nothing asked for one.
- Left the Worker alone. It is another process and already calls `basicConfig` in `step_by_step_worker.main`; the format here matches it so one stack's logs read the same.

Tests — `apps/api/tests/test_logs.py`, at the seam that broke (the app started the way uvicorn starts it, through the test client's lifespan, and the message read off the process's own stdout): a mailed message reaches stdout; it is printed once however often the app starts; uvicorn's own records are neither silenced nor doubled; the app adds exactly one handler and adds it to the root alone. All three failed before the fix.

Also added `apps/api/tests/conftest.py`: starting the app now configures logging process-wide, and a handler keeps the stream it was built with, so an autouse fixture takes our handler off the root after each test. Without it `test_boot.py` leaked a handler bound to its own captured stdout and the new tests failed in a full-suite run while passing alone.

Verified by hand on 2026-08-18, both paths in the criterion: `pnpm --filter api dev` plus `POST /api/auth/request-code` printed `mail from step-by-step@localhost to ada@example.com` with the code, and after `docker compose build api` the `api` container printed the same on 8001 — with uvicorn's startup and access lines still there, once each.

`docs/ARCHITECTURE.md`, mailer section: a paragraph saying `step_by_step_api.logs` is where application log records get their handler, why uvicorn leaves the root without one, and that the Worker configures its own.

`pnpm check`, `pnpm test`, `pnpm test:integration` (stack up), and `pnpm build` all pass; no OpenAPI drift.
