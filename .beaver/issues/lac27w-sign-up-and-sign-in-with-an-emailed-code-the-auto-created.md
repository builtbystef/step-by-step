---
id: lac27w
title: Sign up and sign in with an emailed code; the auto-created Organization
state: todo
priority: high
depends_on:
    - h9gene
    - ycn8xm
parent: ufnuvx
created: 2026-08-14T05:45:06Z
updated: 2026-08-17T04:04:08Z
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
