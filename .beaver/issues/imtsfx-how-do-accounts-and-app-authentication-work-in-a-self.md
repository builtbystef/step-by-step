---
id: imtsfx
title: How do accounts and app authentication work in a self-hosted multi-tenant deployment?
state: done
assignee: claude
priority: medium
labels:
    - roadmap:idnzwf
    - session:grill
depends_on:
    - 8iuuh8
parent: idnzwf
created: 2026-08-08T07:53:28Z
updated: 2026-08-10T23:47:23Z
---

One live interview (grill-me). Tenancy is settled (node 8iuuh8: multi-tenant with personal accounts, no teams/sharing, self-hosted open source, org-hostable). Decide:

- Sign-in method: email/password, OAuth providers, or both — for a self-hosted instance an org runs for its people.
- User provisioning: open signup vs. admin-created accounts vs. invite; is there an instance admin, and what can they do (v1 minimum)?
- Session/token model for the web app, and what the backend issues.
- Password reset and account recovery in a self-hosted deployment (no email service guaranteed).

Related but separate: extension-to-backend authentication stays on the Frontier under extension distribution.

## Notes

**claude** — 2026-08-10T23:47:18Z

Answers (interview 2026-08-10):

SIGN-IN — Email/password only in v1. No OAuth/OIDC dependency: a self-hosted instance cannot assume an identity provider, and every external dependency is a setup step. OIDC is a clean later addition.

PROVISIONING — The first account registered on a fresh instance becomes the Instance Admin. Signup then closes by default; an instance setting reopens it. The admin creates accounts, which start with a temp password. Admin powers (v1, exact): create/disable/delete users, reset passwords, toggle open signup. Tenancy isolation applies to the admin: no visibility into any user's Workflows, Runs, Secrets, or Auth State. Term "Instance Admin" added to docs/GLOSSARY.md.

SESSIONS — The backend issues an opaque session ID in an httpOnly SameSite cookie, backed by a server-side session store (Postgres or Redis — stack has both). Sliding 30-day expiry: each request extends; 30 idle days means logging in again. Revocation is instant via the store (disabling a user kills their sessions). No JWTs — statelessness buys nothing at this scale. The extension's short-lived recording-scoped credential is separate (node n52g83).

PASSWORD RESET & RECOVERY — Admin-driven: the admin sets a temp password and hands it over out of band. Any temp password (reset or admin-created account) forces a password change on first login. No email dependency; SMTP-based self-serve reset can layer on later. Admin lockout: CLI commands inside the backend container (reset-password <email>, promote-admin <email>) — shell access to the host is the trust anchor. Password policy: minimum 8 characters, no complexity rules (NIST guidance).

DISABLE — Sessions die immediately; Schedules stop firing; queued Runs are cancelled; a currently running Run finishes normally (aborting mid-run on an external website can leave half-done real-world actions). Re-enabling resumes Schedules.

DELETE (in v1, user decision overriding the disable-only recommendation) — Hard cascade, irreversible, behind a type-the-username confirmation: the user row and everything owned by it (Workflows, Versions, Schedules, Batches, Runs, Step Results, Artifacts in MinIO, Secrets, Auth State). Queued AND running Runs are cancelled immediately before the purge — a Run acting with the user's secrets must not outlive them. The admin can delete any non-admin user; a user can self-delete; the last remaining admin must promote a successor before self-deleting. No soft delete / grace period.
