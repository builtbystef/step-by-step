---
id: c635m7
title: 'Reveal: the unlock window and the 30-second peek'
state: cancelled
priority: medium
depends_on:
    - 3679bv
    - k678bs
parent: 54i6da
created: 2026-08-14T06:15:09Z
updated: 2026-08-15T04:32:54Z
---

## What to build

The two-stage unlock for reading stored Secret values. Re-entering the account password once opens a 5-minute reveal window recorded on the current session row (the sessions table gains one additive column for it); within the window each value can be revealed individually, and a revealed value re-masks after 30 seconds. Because the window lives on the session, signing out or sign-out-everywhere closes it. Auth State has no reveal in any form.

```
POST /api/secrets/unlock  {password} → 204, opens the window | 401 code=bad_credentials
POST /api/secrets/{id}/reveal        → 200 {value} | 403 code=reveal_locked
```

## Acceptance criteria

- [ ] Reveal with no prior unlock → 403 `reveal_locked`.
- [ ] After unlock with the right password, reveal → 200 with the stored plaintext; the same call 6 minutes later → 403.
- [ ] Unlock with a wrong password → 401 and no window opens — an immediately following reveal still 403s.
- [ ] After sign-out-everywhere, a fresh sign-in's reveal → 403 until unlock runs again.
- [ ] In the Secrets section, revealing shows one row's value and re-masks it after 30 seconds; a second row inside the window needs its own reveal click but no second password entry.
- [ ] The window is per session: unlocking in one browser does not unlock the same account's other sessions.

## Notes

**claude** — 2026-08-15T04:32:54Z

Cancelled in the 2026-08-15 revision of 54i6da: ADR 0005 removed the account password the unlock step re-entered, and the decision is that reveal is ungated — any signed-in member, per-click, 30-second re-mask as a UI courtesy only. The reveal endpoint and re-mask folded into 3679bv; the unlock window, /api/secrets/unlock, and the sessions reveal_unlocked_until column are gone.
