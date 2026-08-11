---
id: b9ur3b
title: 'Spec: accounts and authentication'
state: done
assignee: claude
labels:
    - roadmap:idnzwf
    - session:spec
depends_on:
    - 8iuuh8
    - imtsfx
parent: idnzwf
created: 2026-08-10T23:47:49Z
updated: 2026-08-11T00:59:47Z
---

The accounts area is settled; write its spec (session:spec — read the notes and linked artifacts of this area's closed nodes, interview to close remaining gaps, confirm, then invoke the create-specification skill).

Area nodes: 8iuuh8 (tenancy: multi-tenant personal accounts, self-hosted, ADR 0001) and imtsfx (sign-in, provisioning, Instance Admin, sessions, password reset/recovery, disable and delete semantics).

The spec covers: registration and first-user-becomes-admin bootstrap; the open-signup instance setting; email/password sign-in; the server-side session model (opaque ID, httpOnly SameSite cookie, sliding 30-day expiry); temp passwords and forced change; admin CLI recovery commands; disabling a user (sessions, Schedules, queued vs. running Runs); hard-cascade account deletion (self and admin, last-admin rule, cancellation of in-flight Runs, purge across Postgres and MinIO).

Boundary: the extension's recording-scoped credential belongs to n52g83's ground, not this spec.

## Notes

**claude** — 2026-08-11T00:24:33Z

Gap-closing interview (2026-08-11) — all recommendations accepted. These join the 8iuuh8/imtsfx notes as spec input:

- SESSION STORE — Postgres (not Redis): sessions survive restarts, revocation is SQL, traffic is low. Sliding 30-day expiry with the touch throttled to at most once per hour per session.
- IDENTITY — Email is the sole identity, unique and case-insensitive; optional display name for UI. The hard-delete confirmation types the EMAIL (the roadmap's "type-the-username" line is reworded).
- PROMOTION — CLI-only (promote-admin) in v1; the admin UI powers stay exactly create/disable/delete/reset/toggle-signup. The last remaining admin's self-delete is blocked in the UI with a message pointing at the CLI.
- LOGIN THROTTLING — Per-account: 10 consecutive failures lock the account 15 minutes; admin password reset clears the lock. No CAPTCHA, no IP-based logic.
- HASHING — argon2id with library defaults.
- COOKIE/CSRF — Next.js proxies /api/* to FastAPI so the app is one origin; session cookie is httpOnly, SameSite=Lax, Secure over HTTPS; SameSite=Lax is the whole CSRF story in v1 (no token).
- LOGOUT — Kills the current session; account settings also offers "sign out everywhere" (delete all of the user's session rows).
- DISABLE MID-BATCH — The running Run finishes; the Batch stops and its remaining (not-yet-queued) rows are marked cancelled, consistent with queued-Run cancellation.

Next: user invokes /create-specification for this node; the spec issue publishes with blocking edges back to 8iuuh8 and imtsfx.

**claude** — 2026-08-11T00:59:47Z

Spec published as ufnuvx (Accounts and authentication), label spec, with blocking edges to 8iuuh8 and imtsfx for lineage. Gap answers from this node's interview note are folded into the spec body. Implementation proceeds via create-issues on ufnuvx; sub-issues get built, never the spec issue itself.
