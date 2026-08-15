---
id: 8wxso0
title: 'Recovery CLI: reset-password and promote-admin'
state: cancelled
priority: medium
depends_on:
    - lac27w
    - t7jki2
parent: ufnuvx
created: 2026-08-14T05:46:07Z
updated: 2026-08-15T04:10:06Z
---

## What to build

The lockout escape hatch, with shell access as the trust anchor: two commands runnable inside the backend container against the same database. One resets any account's password to a temp value (printing a generated one when none is given), sets the must-change flag, and clears any lockout; the other promotes a user to Instance Admin — the only promotion path that exists.

## Acceptance criteria

- [ ] Reset with an explicit password → the account signs in with it and gets `{must_change_password: true}`; the old password fails.
- [ ] Reset without a password → the command prints a generated temp password, and signing in with the printed value works the same way.
- [ ] Resetting a locked account clears the lockout: the temp password signs in immediately.
- [ ] Promote → the user's current-user view shows `is_admin: true` and admin routes accept them.
- [ ] Either command with an unknown email → non-zero exit and a clear message; nothing changes.
- [ ] Seam tests invoke the CLI entry point against the same real Postgres the HTTP tests use, covering all of the above.

## Notes

**claude** — 2026-08-15T04:10:06Z

Obsoleted by the 2026-08-15 spec rewrite (ADR 0005): no passwords and no Instance Admin exist, so there is nothing for a recovery CLI to reset or promote — recovery is access to the account email.
