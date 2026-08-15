---
id: 3nxs4k
title: 'Invitations: invite by email, revoke, accept, and the invite-only signup path'
state: todo
priority: medium
depends_on:
    - lac27w
parent: ufnuvx
created: 2026-08-14T05:45:46Z
updated: 2026-08-15T04:11:51Z
---

## What to build

How a team forms: an owner or admin invites an email address into the Organization with a role (admin or member), the Invitation goes out through the mailer seam, and accepting it — signed in with the invited address — creates the Membership. Pending Invitations are listable and revocable and expire after 14 days. Under `SIGNUP_MODE=invite_only`, a pending Invitation is the signup permit: verifying a code for an invited unknown email creates the account (with no auto-created Organization — the invitee starts with only the Invitation to accept). The web app gets a minimal invitations panel and a pending-invitation banner after sign-in; the settings shell re-homes them later.

## Acceptance criteria

- [ ] Owner and admin create an Invitation (email + role admin|member) → 201, and the console mailer captured the Invitation email; a member calling the same route → 403; an unauthenticated caller → 401.
- [ ] Inviting an address that is already a member (any casing) → 409 `already_member`; a second pending Invitation for the same address in the same Organization is refused.
- [ ] Owner and admin list pending Invitations; revoking one → 204, and it can no longer be accepted or seen by the invitee.
- [ ] Signed in with the invited address (case-insensitive), the current user lists the pending Invitation; accepting → 204 and the Organization appears with the invited role. A different account accepting the same Invitation → 404.
- [ ] An Invitation older than 14 days is gone from the pending list and cannot be accepted (clock controlled in tests).
- [ ] `SIGNUP_MODE=invite_only` with a pending Invitation for an unknown email: request-code + verify → 200 `{created: true}`, the account exists with zero Organizations, and the current user lists the Invitation; accepting joins the Organization.
- [ ] The web app shows a pending-invitation banner after sign-in with an accept action, and a minimal invitations panel (list, create, revoke) for owners and admins.
- [ ] HTTP seam tests with a real Postgres cover the role gate, the duplicate and already-member refusals, revocation, acceptance, expiry, and the invite-only signup path end to end.
