---
id: disgge
title: 'Recorder core: click, type, and navigate capture with verified ranked candidates'
state: todo
priority: medium
depends_on:
    - 94xanm
    - bysmhd
parent: d8ux2s
created: 2026-08-14T06:02:56Z
updated: 2026-08-19T01:52:25Z
---

## What to build

The capture pipeline that turns real interactions into semantic Steps. Content scripts in every permitted frame capture interactions and compute the ranked candidate list against the live DOM; the service worker owns the debugger session for computed ARIA role and accessible name; web-navigation events classify navigations. Candidate ranking follows the codegen score order (test-id → role+name → placeholder → label → alt → text → title → CSS), and every persisted candidate is verified at capture to resolve uniquely to the recorded element. The five normative ordering rules each prevent a race the prototype hit: accessibility queried at pointerdown/focusin, never at the action; elements addressed via evaluated object ids, never document node ids; correlation ids scoped per page load; step assembly awaiting the bounded in-flight accessibility query; and every step-producing event flowing through one serialized queue. Captured steps stream to the session's checkpoints. Branch `prototype/mv3-recorder` is the pattern reference — steal patterns, not code. Nothing network-level is ever retained.

## Acceptance criteria

- [ ] A click on `<button data-testid="save">Save</button>` emits a click Step whose candidate list starts with the testid candidate, with a role+name candidate present — role and name from the accessibility tree (implicit roles included), uniqueness verified ignoring ignored nodes.
- [ ] Every persisted candidate resolved uniquely at capture; ranking follows the codegen order.
- [ ] A click that causes navigation emits one click Step marked as asserting navigation and no separate navigate Step; a typed URL change emits a standalone navigate Step.
- [ ] A rapid click sequence emits Steps in interaction order — the serialized queue observable from outside.
- [ ] A fast click that outruns the accessibility query still lands its role+name candidate (assembly awaits the bounded in-flight query), and captures spanning a navigation neither crash nor mix up elements (per-page-load correlation, object-id addressing).
- [ ] Labels are auto-generated at capture and steps carry the envelope defaults; captured steps reach the backend through checkpoints during the recording.
- [ ] The recorder never touches response bodies; no network-level data appears in any emitted message.
- [ ] Extension-boundary tests drive headless Chromium with the unpacked build over local fixture pages and assert on the emitted Step JSON for every example above.

## Notes

**claude** — 2026-08-19T01:52:25Z

The replay half is built (mwrkwp), so the encoding of a candidate's `value` is now pinned by what `step_by_step_worker.selectors` reads. Emit values in these forms, or a candidate verified at capture will not resolve at replay:

- `testid` — the test id itself, read through `get_by_test_id` (Playwright's default attribute, `data-testid`).
- `role` — the body of Playwright's role selector, e.g. `button[name="Save"]`, passed to `locator("role=" + value)`. It carries the accessible name and any further role attributes (`checked`, `level`, …) with Playwright's own quoting rules, which is why replay does not invent a second encoding of role + name.
- `placeholder`, `label`, `alt`, `text`, `title` — the string as written, matched **exactly** (`exact=True`): the recorder verified uniqueness against the real element, and substring matching would resolve to a different element than the one that was verified.
- `css` — a CSS selector, passed as `css=<value>`.
- `shadowPath` — one selector per open shadow-root hop, outermost first; each hop is a scope the next one is read inside, and the last is the scope the candidate itself is read in.

Frames: `resolve` addresses a hop by its `name` when exactly one child frame carries it, and by the recorded `index` otherwise. The `url` is not an address — record it for the person reading the Step.
