---
id: ycn8xm
title: 'The mailer seam: console, SMTP, and Resend adapters'
state: done
assignee: claude
priority: high
parent: ufnuvx
created: 2026-08-15T04:10:00Z
updated: 2026-08-18T08:09:54Z
---

## What to build

One send interface every email in the product goes through, selected by `MAILER=console|smtp|resend` (default console). The console adapter prints the message to the log and doubles as the test capture point; SMTP keeps self-hosting provider-free; Resend is the recommended hosted path. v1 sends exactly two emails — the Sign-in Code and the Invitation — both plain text. Boot fails loudly when the selected adapter's configuration is missing.

## Acceptance criteria

- [ ] A single send seam (to, subject, text body) that callers use; nothing outside it knows which adapter is configured.
- [ ] `MAILER` unset or `console` → sends go to the log and to an in-process capture that seam tests read messages from.
- [ ] `MAILER=smtp` sends through the standard library using `SMTP_HOST`/`SMTP_PORT`/`SMTP_USERNAME`/`SMTP_PASSWORD` (STARTTLS when the server offers it), covered without a live mail server.
- [ ] `MAILER=resend` posts through Resend's HTTP API using `RESEND_API_KEY`, covered against a stubbed HTTP boundary — no live API in tests.
- [ ] `MAIL_FROM` sets the sender address, with a dev default.
- [ ] Selecting an adapter without its required variables → the app refuses to boot with a message naming the missing variable.

## Notes

**claude** — 2026-08-18T08:09:54Z

Built `step_by_step_api.mail` — the one place email leaves the system.

**The seam.** `send(to, subject, text)`; nothing outside it names an adapter. `mailer()` resolves `MAILER=console|smtp|resend` (console by default) once, cached, and `MAIL_FROM` sets the sender with the dev default `step-by-step@localhost`.

**The adapters.** `ConsoleMailer` logs the message and keeps it in an in-process outbox that `outbox()` returns — the capture point every later accounts seam test reads its Sign-in Code from; asking for it while another adapter is configured is an error rather than an `AttributeError`. `SmtpMailer` drives `smtplib` against `SMTP_HOST`/`SMTP_PORT` (587 default), upgrades with STARTTLS **when the server offers it** (a relay on the instance's own host commonly offers none), authenticates when `SMTP_USERNAME`/`SMTP_PASSWORD` are set, and hangs up in a `finally`. `ResendMailer` POSTs `{from, to, subject, text}` to `https://api.resend.com/emails` with a bearer key.

**Boot gate.** The lifespan calls `mailer()` beside `master_key()`, so a selected adapter with missing configuration stops the boot naming the variable — the Sign-in Code being the only way into an instance, a mailer that cannot send must not be found by the first person signing in.

**Decisions made.**
- Blank counts as missing in every variable, because compose passes an unset variable through as an empty string.
- SMTP credentials are all-or-nothing: neither set is an unauthenticated relay; one set makes the other one required and named.
- The SMTP conversation is tested through an `SmtpConnection` protocol the adapter is handed (a recorder in tests, `smtplib.SMTP` in production) and Resend through `httpx.MockTransport` — no mail server, no live API, fast tier.
- A failed send raises whatever the adapter's own library raises. Nothing is wrapped: v1 has no caller that catches one, and inventing a common error type now would be speculative.
- `httpx` moved from `apps/api`'s dev group to its dependencies — it is the Resend adapter's client, and the parent spec names it as the intended one.

**Also landed.** `MAILER`/`MAIL_FROM`/`SMTP_*`/`RESEND_API_KEY` documented in `.env.example` and passed to the `api` service alone in `compose.yaml` (outside the anchor the Workers share — the backend sends every email, a Worker sends none), and a mailer section in `docs/ARCHITECTURE.md`.

19 tests in `apps/api/tests/test_mail.py` plus the boot-gate test; `pnpm run ci` green. No OpenAPI drift — this slice adds no route.
