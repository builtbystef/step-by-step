---
id: ytd6pw
title: Sweep the rows the sign-in flow leaves behind
state: done
assignee: agent
priority: low
labels:
    - maintenance
depends_on:
    - t7jki2
parent: ufnuvx
created: 2026-08-19T10:44:58Z
updated: 2026-08-29T07:40:29Z
---

## What to build

Two accounts tables keep a row per address and nothing ever removes one:

- `signin_codes` — an expired or exhausted code stays until that same address asks for another one, which an address nobody owns never does.
- `signin_code_issuance` — one row per address that has ever been sent a code, kept forever; the throttling slice (t7jki2) reuses the row when the window has passed rather than deleting it.

Requesting a code is unauthenticated and answers 202 for any address, so anybody can put a row in both tables for as many addresses as they can type. The issuance limit caps how many codes one address is sent per hour; it does not cap how many distinct addresses somebody asks about. The rows are tiny and the growth is slow, which is why this is maintenance rather than a bug — but the tables only grow, and no other table in this schema does.

`sessions` shows the shape of the answer: an expired row is deleted where it is found, so ordinary traffic pays for the sweeping. `signin_codes` has the same opportunity (a code is looked up on every verification), and `extension_connect_codes` should be checked for the same thing while here.

## Acceptance criteria

- [ ] An expired Sign-in Code row is gone from `signin_codes` after the flow next touches that address, rather than only being refused.
- [ ] A `signin_code_issuance` row whose window has long passed is removed rather than kept forever, with a rule that says when — and the issuance limit still holds across the removal (an address at its limit stays refused until the window has actually passed).
- [ ] Whatever sweeping is chosen needs no scheduler and no new process: this instance has Workers and a backend, and nothing else.
- [ ] The seam tests are the existing HTTP ones, plus the table assertions that show an absence no answer can carry.

## Notes

**agent** — 2026-08-29T07:36:37Z

Seams: HTTP against the FastAPI app with real Postgres, as the spec already named, plus table lookups that assert an absence no answer can carry (the same extra look test_sessions.py takes for an expired session).

Rule for issuance: a row is removed once its window has closed, paid for by the next successful request-code (any address). An open window is never removed, so an address at its limit stays refused until the hour has actually passed. No scheduler.

extension_connect_codes already sweeps every expired row on issue; nothing to add there.

**agent** — 2026-08-29T07:40:29Z

Swept the leftover sign-in rows on ordinary traffic, no scheduler.

signin_codes — claim deletes an expired row where it is found rather than only refusing it (the sessions pattern). Exhausted-but-unexpired rows still stay until they expire or the next request replaces them; that remains the recovery. Covered by test_a_code_expires_after_ten_minutes asserting the table is empty after the 401.

signin_code_issuance — a row whose window has closed is deleted on the next successful request-code (any address). An open window is never removed, so an address at its limit stays 429 until the hour has actually passed. The sweep sits after the limit check so a 429 does not depend on it. Covered by test_an_issuance_row_is_gone_once_its_window_has_passed and test_sweeping_a_closed_window_does_not_lift_an_open_one.

extension_connect_codes already sweeps every expired row on issue; left alone.

Seams: HTTP plus the table assertions that show an absence no answer can carry.
