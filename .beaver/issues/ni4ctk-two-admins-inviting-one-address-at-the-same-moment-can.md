---
id: ni4ctk
title: Two admins inviting one address at the same moment can leave an Invitation that never accepts
state: todo
priority: low
labels:
    - bug
created: 2026-08-19T00:45:21Z
updated: 2026-08-19T00:45:21Z
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
