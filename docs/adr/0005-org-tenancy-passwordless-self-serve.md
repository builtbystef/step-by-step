# 0005 — Organization tenancy and passwordless self-service

Supersedes ADR 0001.

## Context

The product must remain easy to self-host and may later support a hosted service. Organization ownership is much harder to add after every domain table already exists. Passwords would also require reset, recovery, and storage flows.

## Decision

The Organization is the tenant. Every Workflow, Run, Batch, Schedule, Secret, and Auth State belongs to one Organization.

A new user normally gets an Organization. Users join other Organizations through Invitations. Membership roles are owner, admin, and member. There is no instance administrator; `SIGNUP_MODE` controls whether unknown addresses may sign up.

Authentication uses short-lived Sign-in Codes sent by the console, SMTP, or Resend mail adapter. There are no passwords or password-recovery tools. Sessions are opaque server-side tokens in PostgreSQL with a sliding 30-day idle expiry.

## Reason

Organization ownership supports both teams and future hosted use. Sign-in Codes remove the password lifecycle while keeping email delivery replaceable for self-hosters.
