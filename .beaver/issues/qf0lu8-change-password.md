---
id: qf0lu8
title: Change password
state: cancelled
priority: medium
depends_on:
    - lac27w
parent: ufnuvx
created: 2026-08-14T05:45:34Z
updated: 2026-08-15T04:10:06Z
---

## What to build

A signed-in user changes their own password by proving they know the current one. The same password policy applies to the new value, a successful change clears the must-change flag, and the account area of the web app gains the change-password form. (Nothing sets the must-change flag yet — the admin and CLI slices do — but clearing it is this endpoint's contract.)

## Acceptance criteria

- [ ] Change with the correct current password and a new password of at least 8 characters → 204; the old password now fails sign-in with 401 and the new one succeeds.
- [ ] A wrong current password → refused with a machine-readable error code, and the password is unchanged.
- [ ] A new password of 7 characters → refused, and the password is unchanged.
- [ ] With the must-change flag set on the account, a successful change clears it: fetching the current user afterwards shows `must_change_password: false`.
- [ ] The signed-in web app has a change-password form with distinct messages for wrong-current-password and too-short-new-password.
- [ ] HTTP seam tests with a real Postgres cover all four behaviors, setting the must-change flag through the store for the clearing case.

## Notes

**claude** — 2026-08-15T04:10:06Z

Obsoleted by the 2026-08-15 spec rewrite (ADR 0005): authentication is passwordless Sign-in Codes, so there is no password to change. Nothing replaces this slice.
