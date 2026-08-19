---
id: ni4ctk
title: Two admins inviting one address at the same moment can leave an Invitation that never accepts
state: done
assignee: claude
priority: low
labels:
    - bug
created: 2026-08-19T00:45:21Z
updated: 2026-08-19T00:52:20Z
---

## What is wrong

`offer()` refuses a second standing Invitation for an address by reading the pending list first (`accounts/invitations.py`), which is a check-then-insert with no lock and no constraint behind it. Two admins of the same Organization inviting the same address concurrently both pass the check, and two rows land.

Accepting is then broken for the second row: the first accept creates the Membership, and the second violates the `memberships` primary key — a 500, and a row that answers 500 on every retry, because the failed transaction rolls back and leaves the Invitation standing.

Narrow (it needs two invites in the same instant) and no data is lost, which is why 3nxs4k did not widen its scope to it.

## What would fix it

Either one, not both:

- A unique index over `(org_id, lower(email))` on `invitations` — sturdy, but it also refuses re-inviting an address whose earlier Invitation has expired, unless expired rows are deleted rather than left to lapse. That is a real design change: expiry today is a comparison against `expires_at`, and nothing sweeps.
- A guard in `invitations.accept()`: an address that already holds a Membership spends the Invitation and answers 204 rather than inserting a second one. Three lines, no migration, and it makes "accepting an offer you have already taken" a defined outcome instead of a database error.

## Acceptance criteria

- [ ] Two Invitations for one address in one Organization can no longer leave an id that answers 500 when accepted.
- [ ] A seam test drives whichever state the chosen fix defines, and the existing Invitations tests stay green.

## Notes

**claude** — 2026-08-19T00:52:13Z

Fixed with the second option from the body — the guard in `accept()`, no migration.

**The change.** `invitations.accept()` deletes the locked Invitation row, then returns without inserting when `member_by_email()` already finds a Membership for the address in that Organization. Accepting an offer you have already taken up is now spending it — 204 — rather than a `memberships_pkey` violation, and the role of the offer that was actually accepted stands. The unique index was not taken: it would refuse re-inviting an address whose earlier Invitation lapsed, and expiry here is a comparison against `expires_at` with nothing sweeping, so it would have needed a design change the issue did not ask for.

**Seam.** HTTP against the app with a real Postgres, the tier the rest of the Invitations tests use — `tests/integration/test_invitations.py::test_accepting_a_second_invitation_you_have_already_taken_up_changes_nothing`. The raced second row has no route that makes it (`offer()` refuses one), so the test's `raced_duplicate_of()` helper writes it directly through a session; both accepts and every assertion go over HTTP. It was red with the exact `duplicate key value violates unique constraint "memberships_pkey"` the body describes, green after the guard.

**Facts a reviewer needs.** `member_by_email()` runs after `db.delete(invitation)`; SQLAlchemy autoflush flushes that delete before the membership query, which is harmless — the query reads `memberships`, not `invitations`. The duplicate row still appears in `pending_in`/`offered_to` until it is accepted, which is unchanged and outside this issue.

All checks green: `pnpm check`, `pnpm test` (49 TS + 44 Python), `pnpm test:integration` (69 + 5), `pnpm build` with no OpenAPI drift.
