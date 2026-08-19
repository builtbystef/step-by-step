---
id: x06w5q
title: 'Membership management: roles, removal, leaving, and ownership transfer'
state: done
assignee: claude
priority: medium
depends_on:
    - 3nxs4k
parent: ufnuvx
created: 2026-08-14T05:45:58Z
updated: 2026-08-19T10:36:19Z
---

## What to build

The Membership lifecycle after joining. Any member sees the member list; owners and admins change roles between member and admin and remove members; anyone but the owner can leave; the owner transfers ownership to another member (and becomes an admin). Organizations themselves grow their remaining self-serve controls: rename (owner or admin) and creating an additional Organization. This slice also lands the shared `X-Organization` authorization gate every org-scoped route uses — removal ends access immediately because the Membership check fails. Effects on domain objects (Personal Overrides dying with the Membership) belong to a later slice, once the vault exists.

## Acceptance criteria

- [ ] Any member lists members → 200 with user id, email, display name, role, and join time; a non-member → 403 `not_a_member`.
- [ ] Owner or admin changes a role between member and admin → 200; targeting the owner → 403 `is_owner`; a member calling → 403.
- [ ] Owner or admin removes a member → 204: the removed member's next request with that `X-Organization` → 403 `not_a_member`, while their session and other Organizations still work; removing the owner → 403 `is_owner`.
- [ ] A member or admin leaves (self-removal) → 204 with the same immediate effect; the owner attempting to leave → 403 `is_owner`.
- [ ] Owner transfers ownership to a member → 204: the target's role becomes owner, the old owner becomes admin, and exactly one owner exists throughout; a non-owner calling → 403; a target who is not a member → 404.
- [ ] Owner or admin renames the Organization → 200; a member → 403.
- [ ] Creating an additional Organization → 201 with the caller as owner; it appears in the current user's list.
- [ ] The `X-Organization` gate is one shared dependency: any org-scoped route without a valid Membership in the named Organization → 403 `not_a_member`.
- [ ] The web app has a members screen (roles, remove, leave) and the rename control; the transfer flow names its consequence.
- [ ] HTTP seam tests with a real Postgres cover the full permission matrix, the immediacy of removal, and the transfer.

## Notes

**claude** — 2026-08-19T10:36:17Z

Landed Membership management end to end. `pnpm run ci` green (126 files formatted, no lint or type errors in 66, 124 Vitest and 63 pytest, build with no OpenAPI/client drift) and `pnpm test:integration` green at 102.

WHAT IS THERE

Backend — `accounts/members.py` is the new module: `listing`, `member`, `set_role`, `remove` (removal and leaving, which are one act), and `transfer_ownership`. `accounts/orgs.py` grew the two other widths of its path gate — `PathMembership` (every member's) and `OwningMembership` (the owner's alone, 403 `not_the_owner`) — and `orgs.create`, which `service.create_account` now calls for the signup's auto-created Organization too, so an Organization without an owner is not expressible anywhere. `accounts/routes.py` carries the six routes the spec names: create an Organization, rename it, list members, change a role, remove a member (or leave), transfer ownership.

No migration: the `memberships` table has held everything this needs since `accbfe792ea3`.

Frontend — `apps/web/app/organization/`: `messages.ts` (the refusals, `mayRename`, the `memberControls` table, the transfer's consequence sentence) with its own tests, and `page.tsx`, the screen: one panel per Organization the visitor is in, with the rename control for an owner and an admin, the member list with a role select and Remove, Leave on your own row, and Make owner behind a confirmation that names both halves of what it does.

DECISIONS A REVIEWER SHOULD SEE

1. THE `X-ORGANIZATION` GATE WAS ALREADY ONE SHARED DEPENDENCY — `ActiveMembership`, which lac27w landed and every domain route already declares. What this slice adds is the proof that removal reaches it: `test_members.py` asks a Workflow route with the removed member's session and reads 403 `not_a_member`, and asks the same route in their own Organization and reads 404 `workflow_not_found` — the gate let them through, so what ended was the Membership and not the session.

2. LEAVING AND BEING REMOVED ARE ONE ROUTE, because they are one outcome and differ only in who asked. The gate on it is therefore every member's, and the rule that a member may end their own Membership and nobody else's is in `members.remove` — where the caller's role and the named user are both in hand.

3. ONE REFUSAL PROTECTS THE OWNER. Demoting, removing, and the owner leaving all answer 403 `is_owner`: from a caller's side it is one fact, that the Membership is not theirs to end or to rewrite. Ownership changes by transfer only, and `AssignableRole` (renamed from `InvitedRole`, which was the same two-value type) makes owner inexpressible on the way in — a role change to owner is 422 before it reaches a handler.

4. THE TRANSFER LOCKS BOTH ROWS before writing either, and re-reads the caller's with `populate_existing` so the lock proves something. Two transfers of one Organization cannot both read one owner and leave two: the second waits, finds the caller is no longer the owner, and is refused. Handing it to yourself returns 204 having changed nothing — the alternative would be writing owner and admin onto the one row.

5. THE OLD OWNER STAYS ON AS AN ADMIN. Losing access in the act of handing an Organization on would be a surprise nobody asked for, and they may leave afterwards — which is the test that shows the refusals follow the role rather than the person.

6. THE SCREEN IS ONE TEMPORARY ROUTE, `/organization`, holding the rename and the member list. Settings → Organization → General and → Members are where they belong, and hat4cf re-homes them; there is no shell to hang them in yet. It is reachable and deletable, which is what a temporary home has to be.

7. `memberControls` IS THE BACKEND'S PERMISSION TABLE SAID AGAIN, in one pure function with its own tests. It is not the guard — the guard is the backend's — but a row of controls that would every one of them answer 403 is worse than a row without them.

8. THE MEMBER LIST IS EVERY ROLE'S. Knowing who you work with is not managing them, so the roles that gate the screen's controls do not gate the screen.

9. `join` MOVED INTO `tests/integration/conftest.py`. Making a Membership over HTTP is scaffolding for every test that needs a second person in an Organization, and there was about to be a second copy of it.

NOT VERIFIED IN A BROWSER: Playwright's Chromium could not be installed in this session (no network), so the screen was verified by `next build`'s typecheck and prerender and by its own unit tests, not by hand. The invitations screen beside it was hand-verified in the previous session and shares every primitive this one uses.

CREATING AN ORGANIZATION HAS NO CONTROL ON THE SCREEN — the criterion is the API's, and the acceptance criteria name only the members screen, the rename, and the transfer for the web app. The shell slice gives it a home beside the Organization switcher.
