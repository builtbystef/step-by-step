---
id: ytd6pw
title: Sweep the rows the sign-in flow leaves behind
state: todo
priority: low
labels:
    - maintenance
depends_on:
    - t7jki2
parent: ufnuvx
created: 2026-08-19T10:44:58Z
updated: 2026-08-19T10:44:58Z
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
