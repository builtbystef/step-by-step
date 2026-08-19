---
id: mwrkwp
title: The selector resolution module
state: done
assignee: claude
priority: medium
depends_on:
    - sl7h4j
parent: d8ux2s
created: 2026-08-14T06:02:13Z
updated: 2026-08-19T01:56:17Z
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

## Notes

**claude** — 2026-08-19T01:56:17Z

Done. The replay half of the selector contract: `step_by_step_worker.selectors`, and the browser test tier it needed.

**What landed**

- `apps/worker/src/step_by_step_worker/selectors.py` — `resolve(page, target, deadline, on_walk=None) -> Resolved | SelectorFailure`. It walks a Target's candidates in recorded order and takes the first that matches **exactly one** element; zero and several are the same answer, so no `.first()`, `.nth()`, or `or_()` appears anywhere in the module. A failed walk repeats until the deadline. `Resolved` carries the locator, the matching candidate's `rank`, the `candidate_count`, and the number of `walks`; `SelectorFailure` carries `reason`, a message, and the same two counts.
- `Target.from_document` reads a Target out of the stored Step document — the JSONB shape, `shadowPath` and `frame` included — because that is what a Worker will have in hand.
- `apps/worker/tests/browser/` — the tier's harness: one session-scoped headless Chromium, a loopback HTTP server over `pages/`, and nine fixture pages. Sixteen tests.
- The tier itself: the `browser` pytest marker, deselected by `addopts` alongside `integration`; `pnpm test:browser`; a CI job that installs Playwright's Chromium and runs `pytest -m browser`. `AGENTS.md` and the architecture doc's test-tier and Worker sections say so.

**Decisions**

- **Rank is the zero-based place in the list**, as this issue's first criterion reads it (candidates [testid, role, css] resolving through role records rank 1). `6ewr2p` will write it into `step_results.matched_candidate_rank` unchanged.
- **The deadline is the only clock.** No call in the module waits on Playwright — a candidate is counted, never awaited — so no library default timeout is in play anywhere, which is how "timeouts are always set explicitly" is satisfied without setting one. Between walks it sleeps `min(100 ms, what is left)`.
- **`on_walk` is the seam the executor yields on.** The execution spec (`9gea5p`) has the Run check cancellation and pause "between candidate-walk iterations inside a resolve loop, where nothing has been clicked yet" — without a hook there is no such moment to observe. It is called with each walk's number before the walk starts, and raising from it stops the resolution. It is also what makes the re-walk loop observable from outside, which this issue's fourth criterion asks for.
- **The encoding of a candidate's `value`, pinned here** because the recorder does not exist yet: the plain string for `testid`, `placeholder`, `label`, `alt`, `text`, and `title` (matched `exact=True` — the recorder verified uniqueness against one element, and substring matching would resolve to a different one), a CSS selector for `css`, and the body of Playwright's role selector for `role` (`button[name="Save"]`, passed as `locator("role=" + value)`), which carries name and any further role attributes with Playwright's own quoting rather than a second encoding invented here. `disgge` has this as a note.
- **A frame hop is addressed by its name where exactly one child frame carries it, and by its recorded index otherwise.** A frame that moved keeps its name; a page that renamed nothing is addressed by position as it always was. The recorded `url` is deliberately not an address — frame urls carry session ids and query strings that differ on every visit — so it stays for the person reading the Step.
- **A candidate the engine refuses costs its rank, not the Run.** Candidates are stored data the editor lets a user hand-edit (`m6s5me`), and a malformed CSS selector raises from `Locator.count`. It is skipped like a candidate that matched nothing.
- **A new test tier rather than a stretched existing one.** These tests need a browser and nothing else — no Postgres, no Redis, no compose — so `integration` would have been the wrong word and the wrong CI job. The fast tier stays green on a machine with no browser installed, and the recorder's harness (the spec's second seam) lands in the same tier.

**Facts a reviewer needs**

- Seam: the module itself against local fixture pages through Playwright, as the spec's Testing Decisions name. Every worked example in the criteria has a test; `-m browser` is 16 passing, the fast tier 58, `pnpm run ci` green.
- Mutation-checked, because several of these tests pass against a naive implementation: `count() == 1` → `>= 1` fails the ambiguity test; dropping the frame-name branch fails the moved-frame test; applying only the first shadow hop fails the shadow test (the fixture holds a Save button at the page, in the outer shadow root, and in the inner one, so every hop is load-bearing).
- The frames-and-shadow area the issue warned about held no surprises worth a scar: Playwright's css engine pierces open shadow roots on its own, which is exactly why the shadow fixture had to be built so that each hop is necessary — otherwise the test would have passed without the code under test.
- Left deliberately: the Target dataclasses here are a second reading of a contract `apps/api/.../workflows/document.py` already declares, because the Worker cannot import the backend and `packages/core` carries no document models. Published as `xkfmw8`, and `6ewr2p` — which walks all eight Step types and would otherwise hand-roll the whole document — now depends on it.
- Not built, because no criterion covers them and both belong to the executor: `unsupported` targets are attempted like any other (recording never blocks, and a closed shadow root simply fails at the deadline), and a Target with an empty candidate list burns its deadline rather than failing fast.
