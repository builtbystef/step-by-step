---
id: x06w5q
title: 'Membership management: roles, removal, leaving, and ownership transfer'
state: todo
priority: medium
depends_on:
    - 3nxs4k
parent: ufnuvx
created: 2026-08-14T05:45:58Z
updated: 2026-08-15T04:11:51Z
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
