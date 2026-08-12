---
id: ufnuvx
title: Accounts and authentication
state: todo
labels:
    - spec
depends_on:
    - 8iuuh8
    - imtsfx
created: 2026-08-11T00:59:37Z
updated: 2026-08-11T00:59:37Z
---

## Problem Statement

A self-hosted Step by Step instance serves several people — an org hosts one instance for its staff, or an individual hosts their own. Every Workflow, Run, Batch, Secret, and Auth State belongs to exactly one user, so the instance needs accounts, sign-in, and isolation between users — without depending on any external identity provider or email service, because a self-hosted deployment guarantees neither. Someone must be able to administer users, recover from lockouts with nothing but shell access, and remove a person and every trace of their data.

## Solution

Email/password accounts with server-side sessions. The first account registered on a fresh instance becomes the Instance Admin; signup then closes by default, and an instance setting reopens it. The Instance Admin creates accounts with temp passwords, resets passwords, disables/enables users, deletes users, and toggles open signup — while tenancy isolation keeps every user's content invisible to the admin. Recovery from admin lockout is a CLI inside the backend container, with shell access as the trust anchor. Account deletion is a hard, irreversible cascade behind a type-the-email confirmation.

## User Stories

1. As the first person on a fresh instance, I want my registration to make me the Instance Admin, so that the instance has an administrator without any setup step.
2. As a visitor on an instance with signup closed, I want the registration route to refuse me, so that only provisioned people get accounts.
3. As an Instance Admin, I want to toggle open signup, so that I control how accounts appear.
4. As an Instance Admin, I want to create an account with a temp password handed over out of band, so that I can provision colleagues without an email service.
5. As a user with a temp password, I want to be forced to set my own password on first login, so that nobody else knows my credential.
6. As a user, I want to sign in with email and password and stay signed in for up to 30 idle days, so that I rarely re-authenticate on my own instance.
7. As a user, I want to change my password (knowing the current one), sign out, and sign out everywhere, so that I control my sessions.
8. As a user whose account suffers repeated failed logins, I want the account temporarily locked, so that passwords cannot be brute-forced.
9. As an Instance Admin, I want to reset a user's password to a new temp password, so that a forgotten password is a hand-over, not a support ticket.
10. As an Instance Admin, I want to disable a user so their sessions die, Schedules stop, and pending work is cancelled — and to re-enable them later, so that departures and returns are one switch.
11. As a user (or an Instance Admin acting on a non-admin user), I want account deletion to cancel in-flight Runs and purge everything the account owns, so that nothing of mine outlives my decision to leave.
12. As a locked-out Instance Admin, I want CLI commands in the backend container to reset a password or promote an admin, so that shell access always recovers the instance.

## Implementation Decisions

**Identity.** Email is the sole identity: unique, compared case-insensitively, stored as entered. An optional display name exists for UI. There is no username.

**Password storage and policy.** argon2id with library defaults. Policy: minimum 8 characters, no complexity rules (NIST 800-63B). Any temp password (admin-created account or admin reset) sets a must-change flag; while it is set, every authenticated endpoint except password change and logout returns 403.

**Sessions.** Server-side sessions in Postgres. The token is an opaque random value of at least 128 bits; the store holds its SHA-256, never the token. The cookie is httpOnly, `SameSite=Lax`, `Secure` when served over HTTPS. Sliding 30-day expiry: a request extends the session, but the store is touched at most once per hour per session. Revocation is row deletion. No JWTs. The Next.js frontend proxies `/api/*` to FastAPI so the app is one origin; `SameSite=Lax` is the whole CSRF story — no CSRF token.

**Login throttling.** A per-account counter of consecutive failures; the 10th locks the account for 15 minutes. A successful login or an admin password reset clears counter and lock. No CAPTCHA, no IP-based logic.

**Bootstrap and signup.** Registration succeeds when the instance has zero users (the registrant becomes Instance Admin) or when the open-signup instance setting is on. Otherwise it returns 403. The first-user check is transactional — two concurrent first registrations produce exactly one admin.

**Instance Admin powers** — exactly: create users, disable/enable users, delete non-admin users, reset passwords, toggle open signup. No visibility into any user's Workflows, Runs, Secrets, or Auth State. Promotion is CLI-only.

**Disable.** Disabling a user deletes their sessions, stops their Schedules from firing, and cancels their queued Runs. A currently running Run finishes normally; if it belongs to a Batch, the Batch stops and its remaining rows are marked cancelled. Re-enabling resumes Schedules.

**Delete.** Hard cascade behind a type-the-email confirmation: queued and running Runs are cancelled first (a Run acting with the user's Secrets must not outlive them), then the user row and everything owned by it is purged — Workflows, Drafts, Versions, Schedules, Batches, Runs, Step Results, Secrets, Auth State in Postgres, and the Runs' Artifacts in MinIO. A user self-deletes; an Instance Admin deletes any non-admin user. The last remaining admin cannot self-delete: the UI blocks with a message pointing at the promote-admin CLI.

**HTTP API contract (seam 1).** All routes under the one app origin; errors are JSON with a machine-readable code.

```
POST   /api/auth/register            {email, password, display_name?}         → 201, sets session cookie
                                     403 code=signup_closed | 409 code=email_taken
POST   /api/auth/login               {email, password}                        → 200 {must_change_password: bool}, sets cookie
                                     401 code=bad_credentials | 403 code=account_locked | 403 code=account_disabled
POST   /api/auth/logout                                                       → 204, deletes current session
POST   /api/auth/logout-all                                                   → 204, deletes all of the user's sessions
GET    /api/auth/me                                                           → 200 {id, email, display_name, is_admin, must_change_password}
POST   /api/auth/change-password     {current_password, new_password}         → 204, clears must-change flag
DELETE /api/account                  {email_confirmation}                     → 204, full cascade
                                     403 code=last_admin | 400 code=confirmation_mismatch
GET    /api/admin/users                                                       → 200 [{id, email, display_name, is_admin, is_disabled, created_at}]
POST   /api/admin/users              {email, temp_password}                   → 201, account with must-change flag
POST   /api/admin/users/{id}/reset-password  {temp_password}                  → 204, sets must-change flag, clears lockout
POST   /api/admin/users/{id}/disable                                          → 204
POST   /api/admin/users/{id}/enable                                           → 204
DELETE /api/admin/users/{id}         {email_confirmation}                     → 204, full cascade; 403 code=is_admin
GET    /api/admin/settings                                                    → 200 {open_signup: bool}
PATCH  /api/admin/settings           {open_signup: bool}                      → 200
```

**CLI contract (seam 2)** — commands inside the backend container:

```
reset-password <email> [--password <value>]   sets a temp password (prints a generated one when omitted),
                                              sets the must-change flag, clears any lockout
promote-admin  <email>                        makes the user an Instance Admin
```

**Schema (shape, not migration).** `users`: id, email (unique on lowercase), display_name, password_hash, is_admin, is_disabled, must_change_password, failed_login_count, locked_until, created_at. `sessions`: token_hash (key), user_id, created_at, last_seen_at. `instance_settings`: single row, open_signup.

## Dependencies

- **argon2-cffi** (Python argon2id binding) — the decided hash algorithm; FastAPI's ecosystem has no built-in.

Nothing else: sessions, throttling, and the CLI use Postgres and the standard library.

## Testing Decisions

Seam 1: HTTP tests against the FastAPI app with a real Postgres — external behavior only (status codes, cookies, JSON, and observable effects such as objects gone from MinIO after delete). Seam 2: tests invoke the CLI entry point against the same database. No prior art — this is the codebase's first code.

Worked examples:

- Fresh instance → `register` → 201 and `me` shows `is_admin: true`; a second `register` with signup closed → 403 `signup_closed`.
- 9 failed logins then a correct one → 200 and the counter resets; 10 failed → correct password within 15 minutes → 403 `account_locked`.
- Login with a temp password → `{must_change_password: true}`; `GET /api/auth/me` works, any other endpoint → 403; after `change-password` → 200s again.
- A session last touched 29 days ago → request succeeds and extends; 31 idle days → 401.
- Two requests one minute apart → one `last_seen_at` write.
- Disable a user mid-Batch (row 3 of 10 running) → the running Run finishes, rows 4–10 cancelled, sessions gone, Schedules stop.
- Delete with a wrong `email_confirmation` → 400 and nothing changes; correct → user's rows and MinIO artifacts are gone.
- Last admin `DELETE /api/account` → 403 `last_admin`; after `promote-admin` on another user → 204.

## Out of Scope

- OAuth/OIDC sign-in — clean later addition (imtsfx).
- Email/SMTP self-serve password reset (imtsfx).
- Soft delete or a deletion grace period (imtsfx).
- Teams, sharing, org roles (8iuuh8, ADR 0001).
- Admin demotion (beyond delete), audit logging of admin actions.
- The extension's recording-scoped credential — node n52g83's ground.

## Further Notes

Run cancellation mechanics (states, Worker behavior) are px25yw's ground; this spec only invokes them. The implementation session that builds this lands the stack and checks (issue ymz3md) first. ADR 0001 (multi-tenant self-hosted) applies; ADR 0003's encryption is untouched here beyond deleting Secrets/Auth State rows in the cascade.
