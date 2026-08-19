---
id: t7jki2
title: 'Sign-in Code throttling: attempt caps and issuance limits'
state: done
assignee: claude
priority: medium
depends_on:
    - lac27w
parent: ufnuvx
created: 2026-08-14T05:45:25Z
updated: 2026-08-19T10:46:03Z
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

## Notes

**claude** — 2026-08-19T10:46:03Z

Landed both caps behind the Sign-in Code.

Backend — `codes.py` grew the two limits and the arithmetic behind them. `claim` now answers with an `Attempt` (`accepted` | `wrong` | `exhausted`) instead of a bool: a row whose `attempts` has reached `ATTEMPT_CAP` (5) refuses every further attempt, the right code included, and stays where it is until it expires or the next request replaces it. `count_issuance` counts one request against the address's window and returns where it landed; `service.request_code` refuses with 429 `rate_limited` past `ISSUANCE_LIMIT` (5 an hour) before a code is minted or a message is sent. `service.Verdict` gained `CODE_EXHAUSTED` -> 429, and both routes now declare their 429 in the schema, so the frontend reads a typed `code`.

One migration, `3d5d33364927`, adds `signin_code_issuance`.

Decisions a reviewer should know:

- Issuance is counted in a table of its own rather than on `signin_codes`, because the count has to outlive the code: a code row is deleted the moment it is spent, so a counter living there would be reset by every successful sign-in — and a limit a sign-in resets is not one.
- A fixed window (a counter plus the moment it opened) rather than a log of requests. The limit only ever asks how many, and a row per request would be a table that grows with exactly the spraying it exists to stop.
- The counting is one `INSERT … ON CONFLICT DO UPDATE … RETURNING`, so two requests at once cannot both read four and both write five. The refused request's own increment is rolled back with the rest of its transaction, which is harmless: the count it rolls back to is already at the limit.
- Exhaustion is checked before the digest comparison and after expiry. Before the comparison, because a guesser who has spent five tries must not be handed the sixth by finally getting it right; after expiry, because an expired code is nothing to anybody and `bad_code` is the one answer wrong, expired, spent, and never-issued share.
- `code_exhausted` and `rate_limited` do reveal something `bad_code` does not, and both are worth it: the person at the screen has to know that trying harder is pointless and a fresh code is what they need, and the issuance refusal only tells the caller how often they themselves have asked.

Criteria that were already met, and by what:

- The single-live-code rule is `codes.issue`'s delete-then-insert from lac27w, covered by `test_requesting_a_second_code_retires_the_first` in `tests/integration/test_accounts.py`. `test_a_fresh_code_recovers_an_exhausted_address` is the new half of it: the replacement is also what clears an exhausted code's count.
- The code-entry screen's three distinct messages are in `apps/web/app/signin/messages.ts` with `messages.test.ts`, landed by shurgk against this issue's contract. `bad_code`, `code_exhausted`, and `rate_limited` each read as their own thing, and the screen picks by `code` alone — no frontend change was needed here.

Found and published, not fixed here: ytd6pw — `signin_codes` and the new `signin_code_issuance` both keep a row per address and nothing removes one, so an unauthenticated request-code is a way to make rows for as many addresses as somebody can type. Maintenance rather than a bug: the rows are tiny, but these are the only tables in the schema that only grow.
