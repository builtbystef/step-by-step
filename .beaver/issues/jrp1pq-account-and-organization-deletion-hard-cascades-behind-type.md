---
id: jrp1pq
title: 'Account and Organization deletion: hard cascades behind type-to-confirm'
state: done
assignee: claude
priority: medium
depends_on:
    - x06w5q
parent: ufnuvx
created: 2026-08-14T05:46:20Z
updated: 2026-08-19T10:57:00Z
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

## Notes

**claude** — 2026-08-19T10:57:00Z

Built. `accounts/deletion.py` holds both levels; the routes are DELETE /api/orgs/{org_id} ({name_confirmation}, owner-only) and DELETE /api/account ({email_confirmation}).

Seam (spec's Testing Decisions): HTTP against the app with a real Postgres — `apps/api/tests/integration/test_deletion.py`, nine tests covering both mismatches, the admin/member 403, the sole-owner refusal with both ways out of it (hand the Organization on, or end it), both cascades, and the address signing up again as a stranger.

Facts a reviewer needs:

- No migration. The ownership cascade this slice establishes was already in the schema: every org-owned table references `organizations` with ON DELETE CASCADE and the user-owned rows reference `users` the same way, so one DELETE takes everything. `test_migrations` confirms no drift.
- `signin_codes` is the one row belonging to a user that no cascade reaches — it is keyed by an address, not by an account — so `end_account` deletes it by hand. The issuance count is deliberately left: clearing it would make ending an account a way to ask for another five codes.
- The no-referencing-rows assertion reads Postgres's own catalogue for every FK pointing at `organizations`/`users` rather than a list of tables kept in the test, so a table wired up without a cascade fails it the day it lands.
- Order inside `end_account`: the confirmation is read before the Organizations are, so 403 `sole_owner` only ever reaches somebody who meant to end the account. A mistyped address is 400 `confirmation_mismatch` either way.
- Confirmations: the Organization's name is compared exactly, apart from the whitespace a paste carries; the address is compared without case, like every other comparison of an address here. The frontend's `nameConfirms`/`emailConfirms` say the same, so no button offers what the route would refuse.
- Web: both danger zones sit on the temporary `/organization` and `/account` screens that `hat4cf` re-homes into Settings. Owner-only for the Organization; the account's sole-owner case names the Organizations it still owns and offers a way to the transfer flow instead of a form that cannot work. Decisions and copy are in each screen's `messages.ts` with vitest cover; `deleteAccountAndLeave` joins the sign-out pair in `lib/identity.ts` and throws the refusal rather than swallowing it, so a sole owner keeps their session while they act on it.

Extending the purge over Runs, Artifacts, and Personal Overrides stays o99b7t's.
