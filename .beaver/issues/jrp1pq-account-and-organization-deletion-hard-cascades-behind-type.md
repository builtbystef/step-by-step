---
id: jrp1pq
title: 'Account and Organization deletion: hard cascades behind type-to-confirm'
state: todo
priority: medium
depends_on:
    - x06w5q
parent: ufnuvx
created: 2026-08-14T05:46:20Z
updated: 2026-08-15T04:11:51Z
---

## What to build

Leaving is irreversible and complete, at both levels. The owner deletes an Organization behind typing its name; a user deletes their own account behind typing their email, refused with `sole_owner` while they own any Organization — transfer or delete those first. This slice establishes the two-level ownership-cascade convention every future table joins: org-owned tables cascade from `organizations`, the user-owned rows (sessions, Memberships, Sign-in Codes) cascade from `users`, so no deletion ever leaves a row referencing what is gone. Extending the purge over Workflows, Runs, the vault, and Garage is a separate blocked slice.

## Acceptance criteria

- [ ] Organization delete with a wrong name confirmation → 400 `confirmation_mismatch`, and nothing changes; an admin or member calling → 403.
- [ ] Owner deletes with the correct name → 204: the Organization row, its Memberships, and its pending Invitations are gone; every former member's account, sessions, and other Organizations are untouched, and the org no longer appears in their current-user view.
- [ ] Account self-delete while sole owner of at least one Organization → 403 `sole_owner`, and nothing changes; after transferring ownership (or deleting the Organization), the same request → 204.
- [ ] Account self-delete with a wrong email confirmation → 400 `confirmation_mismatch`, and nothing changes.
- [ ] A successful account delete → 204: sessions die, Memberships end, the user row is gone, no table references the deleted user, and the email can sign up again immediately as a fresh account.
- [ ] The web app has both danger zones: Organization settings offers the owner-only type-the-name delete that warns what goes with it; account settings offers the type-the-email delete, and the sole-owner case explains transfer-or-delete with a path to the transfer flow.
- [ ] HTTP seam tests with a real Postgres cover both mismatches, the sole-owner refusal and its transfer recovery, and both cascades down to no-referencing-rows.
