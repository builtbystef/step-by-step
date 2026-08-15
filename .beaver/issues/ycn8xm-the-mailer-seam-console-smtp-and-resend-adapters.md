---
id: ycn8xm
title: 'The mailer seam: console, SMTP, and Resend adapters'
state: todo
priority: high
parent: ufnuvx
created: 2026-08-15T04:10:00Z
updated: 2026-08-15T04:10:00Z
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
