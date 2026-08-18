---
id: 95v5fm
title: The console mailer's message never reaches the dev log
state: todo
priority: high
labels:
    - bug
created: 2026-08-18T09:30:38Z
updated: 2026-08-18T09:30:38Z
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
