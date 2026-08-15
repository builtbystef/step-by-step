---
id: mwrkwp
title: The selector resolution module
state: todo
priority: medium
depends_on:
    - sl7h4j
parent: d8ux2s
created: 2026-08-14T06:02:13Z
updated: 2026-08-14T06:02:13Z
---

## What to build

The replay half of the selector contract, the module the Workers will consume. It takes a page, a Target from the step document, and a deadline, and returns the element or a typed failure:

```
resolve(page, target, deadline) -> Element | SelectorFailure

Walk candidates in rank order; the first resolving to exactly one element
wins. Zero or several matches -> skip the candidate: ambiguity is always
rejected; .first()/.nth()/locator.or() are never used. If the whole list
fails, re-walk it in a loop until the step timeout expires — the timeout
IS the retry budget; no separate retry counter. On success, record the
matched candidate's rank (the Selector Drift signal). On expiry -> failure.
```

Timeouts are always set explicitly. Frames and open-shadow-root hops in the Target are honored; this area was researched but never prototyped, so budget for surprises there.

## Acceptance criteria

- [ ] Candidates [testid, role+name, css] where the testid element is gone and role+name matches exactly one element → resolves via the rank-1 candidate, and the result records rank 1.
- [ ] A candidate matching two elements is skipped and resolution continues down the list — even though a `.first()` would have "worked".
- [ ] With every candidate ambiguous or missing → SelectorFailure at the deadline, not before it.
- [ ] An element that appears 2 s after navigation, with a 30 s timeout → resolved; the re-walk loop is observable from outside.
- [ ] A Target with a shadow path resolves through open shadow roots hop by hop; a Target with a frame path resolves inside the addressed frame.
- [ ] Pure-module tests run against local fixture pages through Playwright and cover every example above.
