---
id: t7jki2
title: 'Sign-in Code throttling: attempt caps and issuance limits'
state: todo
priority: medium
depends_on:
    - lac27w
parent: ufnuvx
created: 2026-08-14T05:45:25Z
updated: 2026-08-15T04:11:51Z
---

## What to build

A 6-digit Sign-in Code is brute-forceable without caps, so throttling is part of the auth story: a per-code attempt cap kills a code after repeated wrong guesses, and a per-email issuance limit stops code spraying — the one exception to request-code's always-202 contract. Requesting a new code invalidates the previous one, so at most one code per email is ever live. No CAPTCHA and no IP-based logic. The code-entry screen tells each failure apart.

## Acceptance criteria

- [ ] Five wrong guesses against a code → each 401 `bad_code`; a sixth attempt, even with the correct code → 429 `code_exhausted`; requesting a fresh code recovers.
- [ ] Attempts against one email's code never affect another email.
- [ ] Five code requests for one email within an hour → 202 each; the sixth → 429 `rate_limited`; once the window passes, a request succeeds again (clock controlled in tests, not waited out).
- [ ] Requesting a new code invalidates the previous one: the older code → 401 `bad_code` even within its 10 minutes.
- [ ] The web code-entry screen shows distinct messages for a wrong code, an exhausted code (ask for a new one), and rate limiting (wait before requesting another).
- [ ] HTTP seam tests with a real Postgres cover the cap, the isolation between emails, the issuance limit and its expiry, and the single-live-code rule.
