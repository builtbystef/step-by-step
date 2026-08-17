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
updated: 2026-08-15T04:08:32Z
---

## Problem Statement

Step by Step ships as MIT self-hosted open source today and should be able to become a hosted SaaS later without a tenancy rewrite. The tenant is therefore the Organization (ADR 0005): every Workflow, Run, Batch, Schedule, Secret, and Auth State belongs to exactly one Organization, and users act inside Organizations through Memberships. The instance needs self-serve accounts, sign-in without passwords, Organizations with roles and Invitations, and clean removal of a member, an account, or a whole Organization — with no instance-level administrator anywhere.

## Solution

Passwordless email accounts with server-side sessions. Signing in and signing up are one flow: the visitor enters an email, receives a Sign-in Code through the mailer seam (Resend, SMTP, or console adapter), and enters it. If no account exists and signup allows it, verifying the code creates the account and auto-creates an Organization with the new user as owner. Users join further Organizations by Invitation; roles are owner, admin, and member. A signup-mode environment variable (open or invite-only) replaces the Instance Admin's toggle; recovery is email access itself, so no recovery CLI exists. Deletion is self-serve and hard: an owner deletes an Organization (full cascade), a user deletes their own account.

## User Stories

1. As a visitor, I want to enter my email and the code it receives to get an account with my own Organization ready, so that starting takes one step and no password exists to manage.
2. As a returning user, I want the same email-plus-code flow to sign me in, so that there is nothing to remember or reset.
3. As a user, I want to stay signed in for up to 30 idle days, sign out, and sign out everywhere, so that I control my sessions.
4. As an attacker guessing codes or spraying requests, I want to be stopped by attempt caps and issuance limits, so that a 6-digit code is not brute-forceable. (Adversarial story — the instance's, really.)
5. As an org owner or admin, I want to invite an email address with a role and revoke pending Invitations, so that my team joins without any instance operator involved.
6. As an invitee, I want signing in with the invited address to surface the Invitation and accepting it to land me in the Organization, so that joining is one sign-in.
7. As an org owner or admin, I want to change member roles and remove members, so that access tracks the team.
8. As an org owner, I want to rename the Organization, transfer ownership, and delete the Organization behind a type-the-name confirmation, so that its lifecycle is mine.
9. As a member of several Organizations, I want an active-organization context the app remembers, so that everything I see and create is unambiguously scoped.
10. As a user, I want account deletion to be a type-the-email hard delete, refused while I am the sole owner of any Organization, so that leaving is complete but never silently destroys a team's work.
11. As a self-hoster, I want signup mode and the mail adapter to be environment variables, so that an exposed instance can be invite-only and an air-gapped one can use SMTP or the console.

## Implementation Decisions

**Identity.** Email is the sole identity: unique, compared case-insensitively, stored as entered. Optional display name. No usernames, no passwords, and no separate email-verification step — every sign-in proves the address.

**Sign-in Codes.** 6 decimal digits, generated from a CSPRNG; the store holds a hash, never the code. One code per request, valid 10 minutes, single-use, and dead after 5 failed attempts. Requesting a code always returns 202 regardless of whether an account exists (no account-existence oracle); the email says whether it is a sign-in or a sign-up. Throttling is its own slice: per-email issuance limits and the attempt cap. No CAPTCHA, no IP-based logic.

**Signup mode.** `SIGNUP_MODE=open|invite-only`, default `open`. Under `open`, verifying a code for an unknown email creates the account. Under `invite-only`, it does so only when a pending Invitation exists for that address; otherwise 403 `signup_closed`. There is no instance settings table and no instance admin.

**The auto-created Organization.** Account creation creates an Organization named after the email's local part (renameable), with the new user as owner. Every user therefore always has at least one Membership — except a user who joined by Invitation under invite-only mode, who starts with only the invited Membership and may create Organizations later.

**Sessions** — unchanged from the password-era design. Server-side sessions in Postgres; opaque token of at least 128 bits, stored as SHA-256; cookie httpOnly, `SameSite=Lax`, `Secure` over HTTPS; sliding 30-day expiry touched at most once per hour; revocation is row deletion; no JWTs; one origin via the Next.js proxy, `SameSite=Lax` is the whole CSRF story.

**Organization context.** Domain routes keep their flat paths (`/api/workflows`, …). The acting Organization travels in a required `X-Organization` header that the frontend's fetch wrapper sets from the active-organization choice; the backend authorizes the session's user's Membership in it on every request. This keeps every other spec's path contract intact.

**Roles** — exactly three. Owner (exactly one per Organization): everything, plus rename, transfer ownership, and delete the Organization. Admin: manage Invitations and members (invite, revoke, change roles between member and admin, remove members — never the owner). Member: all domain work (Workflows, Runs, Batches, Schedules, vault use). Roles gate membership and lifecycle actions only; domain work is open to every role.

**Invitations.** Email plus role (admin or member), created by owner or admin; sending goes through the mailer seam. Pending Invitations are listable and revocable; they expire after 14 days; inviting an already-member address is a 409. Accepting requires being signed in with the invited address (case-insensitive); sign-in surfaces pending Invitations. An Invitation is the signup permit under invite-only mode.

**Removal and leaving.** Removing a member (or leaving) ends the Membership immediately: org content disappears from their app, and their Personal Overrides in that Organization's vault are deleted. Nothing else stops — Schedules, Runs, and Batches belong to the Organization, not the member. The owner cannot be removed and cannot leave without first transferring ownership. There is no per-user disable.

**Organization deletion.** Owner-only, behind typing the Organization's name. Queued and running Runs are cancelled first (a Run acting with the Organization's Secrets must not outlive them), then everything the Organization owns is purged — Workflows, Drafts, Versions, Schedules, Batches, Runs, Step Results, Secrets, Auth State, Personal Overrides, Invitations, Memberships in Postgres, and the Runs' Artifacts in Garage.

**Account deletion.** Self-serve, behind typing the account email. Refused with 403 `sole_owner` while the user owns any Organization — transfer or delete those first. Otherwise: end all Memberships (with the removal semantics above), delete sessions, pending codes, and the user row. Hard, irreversible, no grace period.

**The mailer seam.** `MAILER=console|smtp|resend` selects an adapter behind one send interface; Resend is the recommended hosted path (`RESEND_API_KEY`), SMTP keeps self-hosting provider-free, console prints to the log for dev — and doubles as the test capture point. Boot fails loudly on missing adapter config. v1 sends exactly two emails: the Sign-in Code and the Invitation.

**HTTP API contract (seam 1).** All routes under the one app origin; errors are JSON with a machine-readable code.

```
GET    /api/instance                                                → 200 {signup_mode: "open"|"invite_only"}   (unauthenticated)
POST   /api/auth/request-code        {email}                        → 202 always (rate limits excepted: 429 code=rate_limited)
POST   /api/auth/verify-code         {email, code}                  → 200 {created: bool}, sets session cookie
                                     401 code=bad_code | 403 code=signup_closed | 429 code=code_exhausted
POST   /api/auth/logout                                             → 204, deletes current session
POST   /api/auth/logout-all                                         → 204, deletes all of the user's sessions
GET    /api/auth/me                                                 → 200 {id, email, display_name,
                                                                            orgs: [{id, name, role}], invitations: [{id, org_name, role}]}
PATCH  /api/account                  {display_name}                 → 200
DELETE /api/account                  {email_confirmation}           → 204 | 403 code=sole_owner | 400 code=confirmation_mismatch

POST   /api/orgs                     {name}                         → 201, creator becomes owner
PATCH  /api/orgs/{id}                {name}                         → 200 (owner or admin)
DELETE /api/orgs/{id}                {name_confirmation}            → 204, full cascade (owner) | 400 code=confirmation_mismatch
POST   /api/orgs/{id}/transfer-ownership  {user_id}                 → 204 (owner; target must be a member)
GET    /api/orgs/{id}/members                                       → 200 [{user_id, email, display_name, role, joined_at}]
PATCH  /api/orgs/{id}/members/{user_id}   {role}                    → 200 | 403 code=is_owner
DELETE /api/orgs/{id}/members/{user_id}                             → 204 (admin/owner removes; self = leave) | 403 code=is_owner
GET    /api/orgs/{id}/invitations                                   → 200 pending list
POST   /api/orgs/{id}/invitations    {email, role}                  → 201, email sent | 409 code=already_member
DELETE /api/orgs/{id}/invitations/{invitation_id}                   → 204, revoked
POST   /api/invitations/{id}/accept                                 → 204, creates the Membership
```

Domain routes (other specs) additionally require the `X-Organization` header; a session without a Membership in it → 403 `not_a_member`.

**Schema (shape, not migration).** `users`: id, email (unique on lowercase), display_name, created_at. `sessions`: token_hash (key), user_id, created_at, last_seen_at. `signin_codes`: id, email, code_hash, attempts, expires_at, created_at. `organizations`: id, name, created_at. `memberships`: org_id + user_id (unique pair), role, created_at. `invitations`: id, org_id, email, role, expires_at, created_at. Ownership-cascade convention: every org-owned table references `organizations` with cascade; the few user-owned rows (sessions, Personal Overrides, Memberships) cascade from `users`.

## Dependencies

- **Mailer adapters**: Resend via its HTTP API (httpx — already a FastAPI-world dependency), SMTP via the standard library's `smtplib`, console via logging. No password-hashing library — argon2 leaves with the passwords.

## Testing Decisions

Seam: HTTP tests against the FastAPI app with a real Postgres — external behavior only. The console mailer is the capture point: tests read the emitted code/invitation from it rather than reaching into tables.

Worked examples:

- Fresh instance, `SIGNUP_MODE=open`: request-code → 202; verify with the captured code → 200 `{created: true}` with a cookie; `me` shows one org, role owner, named after the email's local part.
- Same email again: request + verify → `{created: false}` and the same account.
- `SIGNUP_MODE=invite_only`, unknown email, no Invitation: request-code → 202 (no oracle); verify with the correct code → 403 `signup_closed`. With a pending Invitation for that address: → 200 `{created: true}`, and `me` lists the Invitation for accepting.
- Wrong code five times → each 401 `bad_code`; the correct code afterwards → 429 `code_exhausted`; a code from a previous request → 401 (single-use, newest-only is acceptable).
- A session last touched 29 days ago → extends; 31 idle days → 401. Two requests a minute apart → one `last_seen_at` write.
- Admin invites `b@x.com` as member → 201 and the console mailer captured an Invitation email; a member calling the same route → 403.
- Removing a member: their next request with that `X-Organization` → 403 `not_a_member`, their session elsewhere still works, and the Organization's Schedules keep firing.
- Owner deletes the Organization with the typed name → 204; its rows and its Runs' Garage objects are gone; members' accounts survive.
- Sole owner of one org calls `DELETE /api/account` → 403 `sole_owner`; after transfer-ownership → 204, and the org's work is untouched.

## Out of Scope

- Billing, plans, entitlements, seat limits — the SaaS layer waits for demand.
- OAuth/OIDC/SSO sign-in; magic sign-in links (click-to-sign-in) — the code is the v1 flow.
- Multiple owners per Organization; custom roles; audit logging of membership actions.
- Per-user disable (removed with the Instance Admin), recovery CLI (email access is recovery).
- The extension's recording-scoped credential — node n52g83's ground.

## Further Notes

ADR 0005 records this model and supersedes ADR 0001. Run cancellation mechanics remain px25yw's ground; Organization deletion invokes them. The vault spec (54i6da) owns Personal Override storage and run-time resolution (a Run started by a member uses that member's overrides; Scheduled Runs use the shared org values); this spec only defines the terms and the deletion hooks. Sessions, sliding expiry, and sign-out-everywhere carry over from the password-era design unchanged.

## Notes

**claude** — 2026-08-15T04:08:32Z

Rewritten 2026-08-15 for ADR 0005: Organization tenancy (auto-org at signup, owner/admin/member, Invitations), passwordless Sign-in Code auth through a mailer seam (Resend/SMTP/console), SIGNUP_MODE env var replacing the Instance Admin, self-serve org and account deletion. Sessions model unchanged. Supersedes the email/password + Instance Admin body this spec previously carried (see git history).
