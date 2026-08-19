---
id: 3nxs4k
title: 'Invitations: invite by email, revoke, accept, and the invite-only signup path'
state: done
assignee: claude
priority: medium
depends_on:
    - lac27w
parent: ufnuvx
created: 2026-08-14T05:45:46Z
updated: 2026-08-19T00:45:49Z
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

## Notes

**claude** — 2026-08-19T00:45:49Z

Landed Invitations end to end. `pnpm run ci` green (90 files formatted, no lint or type errors in 48, 49 Vitest and 44 pytest, build with no OpenAPI/client drift) and `pnpm test:integration` green at 68.

WHAT IS THERE

Backend — `accounts/invitations.py` is the new module: `pending_in` / `pending_for`, `offer` (which mails through the seam), `revoke`, and `accept`. `accounts/orgs.py` grew `membership_in` and `ManagingMembership`, the same Membership lookup with a role gate, on a path that names its Organization. `accounts/routes.py` carries the four routes the spec names — list, create, revoke, accept — plus the `invitations: [{id, org_name, role}]` field on `GET /api/auth/me` that lac27w deliberately left out. `accounts/service.py` gained `may_sign_up`, which is the invite-only signup permit.

No migration: the `invitations` table landed with the accounts schema in `accbfe792ea3`, columns and all.

Frontend — `apps/web/app/invitations/`: `messages.ts` (the refusals, `manageableOrgs`, the banner sentence) with its own tests, and `page.tsx`, the screen. Verified by hand in Chrome against the real stack: ada signs up, invites grace as admin, sees the row and the `already_invited` refusal on a second invite of `GRACE@…`; grace signs in, lands on the banner ("ada invited you to join as an admin"), accepts, and comes back with panels for both Organizations. The Invitation email appears in the dev log through the console mailer.

DECISIONS A REVIEWER SHOULD SEE

1. THE INVITATIONS SCREEN IS ONE TEMPORARY ROUTE, `/invitations`, holding both halves. The banner belongs in the shell's chrome and the panel inside Settings → Organization — the path `lib/gate.ts` already reserves and already redirects members away from — and hat4cf re-homes both. Neither has a home today: there is no shell, and `HOME_PATH` (`/workflows`) is not a route yet. It is reachable and it is deletable, which is what a temporary home has to be. Signing in from a link to it lands on it, because `landingAfterSignIn` honours `next`, which is how the "banner after sign-in" was verified.

2. A MEMBER IS TOLD `not_an_admin`, NOT `not_a_member`. They are in this Organization; refusing with a code that says otherwise would hide a fact they already hold. `not_a_member` stays what it is — the caller is not in the Organization at all — so `orgs.py` has one gate with two refusals rather than two gates.

3. REVOKED, EXPIRED, TAKEN, AND NEVER MADE ALL ANSWER 404 `invitation_not_found`, and so does an offer made to somebody else's address. An id another account holds must not be confirmable by guessing at it, which is the same rule the Workflow routes follow for another Organization's Workflow.

4. THE INVITE-ONLY PERMIT IS ONE RULE WITH TWO READERS. `may_sign_up(db, address)` is "open, or invited", and both `request_code` and `verify_code` ask it. That is what lets the email say the truth the 202 must not: an invited unknown address is told the code creates its account, an uninvited one gets the sign-in wording, and the answer to the request is identical either way — the mail reaches the mailbox and nobody else, so it is not an oracle.

5. AN ACCOUNT CREATED BY AN INVITATION UNDER INVITE-ONLY GETS NO ORGANIZATION. `create_account` takes `with_organization` for it. They came to join one that already exists, and an empty Organization named after their address is one nobody asked for. Under `open` an invited signup still gets its own, which is the spec's rule.

6. THE ROLE ON THE WAY IN IS ITS OWN TWO-VALUE TYPE. `InvitedRole` is admin|member, so the generated client hands the panel's select a union it cannot get wrong, and owner — of which there is exactly one, and which transfers rather than being offered — is not expressible. The answers still carry the stored `Role`.

7. ACCEPT LOCKS THE ROW before deleting it, so two accepts of one offer make one Membership.

8. THE EXPIRY IS A COMPARISON, NOT A SWEEP. An Invitation past 14 days stays in the table and is absent from both lists and from accept. Nothing has to run for a Membership not to be created.

FOUND AND PUBLISHED, NOT FIXED HERE: ni4ctk — two admins inviting one address in the same instant defeat the check-then-insert behind `already_invited`, and the second row then answers 500 on accept forever. Narrow, no data lost, and the fix (a unique index, or a guard in accept) is a decision of its own.
