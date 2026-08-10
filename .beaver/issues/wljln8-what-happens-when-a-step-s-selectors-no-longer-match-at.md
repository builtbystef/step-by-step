---
id: wljln8
title: What happens when a step's selectors no longer match at replay?
state: todo
priority: medium
labels:
    - roadmap:idnzwf
    - session:grill
depends_on:
    - ds8zyn
parent: idnzwf
created: 2026-08-08T08:11:55Z
updated: 2026-08-08T08:11:55Z
---

The recorder research (`f10wq3`) settled what a step *stores*: a ranked list of alternative selectors, each verified unique at record time. This node settles what the runner *does* with that list when the page has changed, and what the user sees.

Decide:

- **Resolution policy.** Ordered fallback (try candidates by rank; first that resolves to exactly one element wins) or weighted voting across all candidates? The evidence in `f10wq3` favours voting for XPath-era locators (29.5% better than the best single strategy) but was measured without role/test-id locators, and voting has a documented failure mode where broken locators converge on the wrong element. Ordered fallback is simpler and probably enough with a test-id or role+name at the top.
- **Ambiguity.** Playwright is strict: a locator matching several elements throws. A recorded selector that has become ambiguous should almost certainly be rejected in favour of the next candidate rather than resolved with `.first()` — confirm, and decide whether ambiguity is ever acceptable.
- **Drift visibility.** Record which candidate resolved. A step running on its 4th-ranked selector is a warning the user should see before the step fails outright. Where does that surface — run detail, workflow editor, both?
- **Retries and timeouts.** Playwright's actionability checks (visible, stable, enabled, receives events) already wait. What retry policy sits on top, and what per-step timeout? (Python binding defaults to 30s; set it explicitly.)
- **Partial runs.** When a step fails for good: abort the run, or continue? What is the run's terminal state, and what happens to a batch when one row's run fails? Coordinate with the execution architecture node (`px25yw`) on where this policy lives.
- **Repair path.** When a selector is dead, what does the user do — re-record the single step, pick the element again, edit by hand? This is the difference between a workflow that survives and one that gets abandoned.

Out of scope here: DOM-tree-comparison self-healing and automatic selector regeneration, both excluded for v1 (see the roadmap's Out of scope).

Read the research note on `f10wq3` before this session — it has the Playwright strictness, actionability, and locator-fallback specifics with citations.
