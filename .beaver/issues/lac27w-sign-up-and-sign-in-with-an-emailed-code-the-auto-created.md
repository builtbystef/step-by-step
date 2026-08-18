---
id: lac27w
title: Sign up and sign in with an emailed code; the auto-created Organization
state: done
assignee: claude
priority: high
depends_on:
    - h9gene
    - ycn8xm
parent: ufnuvx
created: 2026-08-14T05:45:06Z
updated: 2026-08-18T09:31:53Z
---

## What to build

The core tracer through accounts, passwordless: a visitor enters an email, a Sign-in Code goes out through the mailer seam, and verifying it signs them in — creating, for an unknown email under `SIGNUP_MODE=open`, the account plus an auto-created Organization owned by it. Sign-in issues a server-side session carried by a cookie; the user can see who they are and sign out. This slice lands the full accounts schema (users, sessions, signin_codes, organizations, memberships, invitations — including the columns later slices animate, such as the attempt counter and invitation expiry), the unauthenticated `/api/instance` endpoint, and a minimal two-step sign-in page in the web app using the generated client. All errors are JSON with a machine-readable code.

## Acceptance criteria

- [ ] Requesting a code → 202 whether or not an account exists for the email; the console mailer captures a 6-digit code; the store holds a hash of the code, never the code.
- [ ] Verifying the captured code for a fresh email (`SIGNUP_MODE=open`) → 200 `{created: true}` with a session cookie that is httpOnly and `SameSite=Lax` (`Secure` over HTTPS); the current user shows the email exactly as entered and one Organization, named after the email's local part, with role owner.
- [ ] Email is the sole identity, unique case-insensitively but stored as entered: request + verify for `Ada@Example.com` after `ada@example.com` signs into the same account with `{created: false}`, and no second Organization appears.
- [ ] Codes are single-use and expire after 10 minutes: verifying an already-used code → 401 `bad_code`; an expired code → 401 `bad_code` (clock controlled in tests). Attempt caps and issuance limits are the throttling slice; the schema columns for them exist now.
- [ ] `SIGNUP_MODE=invite_only`, unknown email, no pending Invitation: request-code still → 202 (no account-existence oracle), verify with the correct code → 403 `signup_closed`, and no user or Organization rows exist afterwards. (The invited path lands with the Invitations slice.)
- [ ] The session token is an opaque random value of at least 128 bits; the store holds only its SHA-256; no JWTs anywhere.
- [ ] Fetching the current user without a valid session → 401. Sign-out → 204, the session row is deleted, and the next request with the old cookie → 401.
- [ ] `GET /api/instance` unauthenticated → 200 `{signup_mode}` reflecting the environment variable, defaulting to `open`.
- [ ] The web app has a two-step sign-in screen (email → code entry) used for both first and returning visits; when signed in, the UI shows the account's email; the frontend talks only through the generated client behind the one-origin proxy.
- [ ] Seam tests are HTTP against the app with a real Postgres, reading codes from the console mailer's capture, covering every status code and cookie behavior above.

## Notes

**claude** — 2026-08-17T04:04:08Z

Scope addition: also land PATCH /api/account {display_name} → 200 (session-authed, no X-Organization needed). ufnuvx names the route but no slice owned it; the Settings account panel (hat4cf) consumes it.

**claude** — 2026-08-18T09:31:53Z

Landed the accounts tracer end to end.

Backend — `step_by_step_api.accounts` in five modules: `models.py` (the six tables), `codes.py` (Sign-in Codes), `sessions.py` (opaque token, cookie, the CurrentUser dependency), `service.py` (sign-up/sign-in as one flow, SIGNUP_MODE), `routes.py` (the HTTP surface). Plus `errors.py` (the {code, message} refusal shape, and the `errors(...)` helper that puts it in the OpenAPI schema so the frontend reads a typed `code`) and `clock.py` (the one place time enters, which is how the expiry test controls it). Routes: GET /api/instance, POST /api/auth/request-code, POST /api/auth/verify-code, GET /api/auth/me, POST /api/auth/logout, PATCH /api/account.

One migration, `accbfe792ea3`, holds all six tables including the columns later slices animate.

Frontend — `apps/web/app/page.tsx` replaced with the minimal two-step screen; verified by hand in Chrome against the real stack: `Grace@Example.com` -> code -> signed in, showing the address as entered and the Organization `Grace` with role owner, a wrong code showing the bad_code refusal, and sign-out returning to step one.

Decisions a reviewer should know:

- Seam: HTTP against the app with a real Postgres, reading codes from the console mailer's outbox (the spec's Testing Decisions). Two tests do read a table, and both assert an *absence* no HTTP answer can carry: no user or Organization row after a signup_closed refusal, and no code or session token held in the clear.
- Tables live in the backend (`step_by_step_api.accounts.models`), not in `packages/core`. Core owns connections, never schema, per ARCHITECTURE. A later domain slice whose Worker-written tables need an org_id FK may have to move them; that is that slice's call.
- The Sign-in Code is stored as a plain SHA-256. The spec rules out a password-hashing library, and a digest is no defence against brute-forcing a six-digit number offline; the protections are the ten minutes, the single use, and the attempt cap (t7jki2). What the digest buys is that a leaked backup hands nobody a working code. Documented in `codes.py`.
- `verify_code` returns a verdict rather than raising, so the route commits before it refuses: a counted wrong guess and a spent code must survive the answer that carries them. Under invite_only the correct code is therefore spent even though signup is refused; the criterion only requires that no user or Organization row remains, and it does not.
- `SIGNUP_MODE` accepts `invite-only` as well as `invite_only`, because the spec's prose writes it with a hyphen and a self-hoster copying that word should get an invite-only instance, not a boot failure. It is read per request and proven at boot beside the master key and the mailer, so a typo stops the process while an operator is watching.
- `GET /api/auth/me` deliberately does NOT carry the spec's `invitations` field. Nothing in this slice creates an Invitation, and 3nxs4k explicitly owns 'the current user lists the pending Invitation'. An always-empty field would be shape without behaviour; 3nxs4k adds it, additively.
- The invited signup path under invite_only is likewise 3nxs4k's: here, invite_only plus an unknown address is always 403 signup_closed.
- Logout requires a session (401 without one). Sliding expiry and logout-all stay with k678bs; the cookie's 30-day Max-Age is set, the server-side touch is not.

Also: SIGNUP_MODE added to .env.example and to the api service in compose.yaml (on the api alone, like the mailer — the Workers serve no one). ARCHITECTURE.md gained the Accounts, Errors, Clock, and frontend-data-layer sections and the note that schema is declared in the backend.

Found and published, not fixed here: 95v5fm — the console mailer's message never reaches the dev log, because plain uvicorn configures no root handler. A default `MAILER=console` dev instance therefore shows nobody their Sign-in Code. The seam tests read the in-process outbox, so they never saw it.
