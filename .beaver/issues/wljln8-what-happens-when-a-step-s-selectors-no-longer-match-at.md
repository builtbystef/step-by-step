---
id: wljln8
title: What happens when a step's selectors no longer match at replay?
state: done
assignee: claude
priority: medium
labels:
    - roadmap:idnzwf
    - session:grill
depends_on:
    - ds8zyn
parent: idnzwf
created: 2026-08-08T08:11:55Z
updated: 2026-08-11T01:27:31Z
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

## Notes

**claude** — 2026-08-11T01:27:31Z

## Question

What does the runner do when a step's ranked selector list no longer matches at replay, and what does the user see?

## Answer

**Resolution policy — ordered fallback, own loop.** Walk the candidates by rank; the first that resolves to exactly one element wins, and the action runs on it. Implemented as our own resolve-and-count loop, never `locator.or()` (its union match trips Playwright strict mode precisely when two alternatives both still match). Weighted voting stays excluded (roadmap Out of scope): with a test-id or role+name candidate at the top, first-match-wins captures nearly all the measured benefit, without voting's documented wrong-element convergence failure.

**Ambiguity — always reject, no exceptions.** A candidate that now matches several elements is skipped in favor of the next candidate; `.first()` is never used to disambiguate. Playwright's docs are explicit that an ambiguous match after a page change may point at a completely different element. If every candidate is ambiguous or missing, the step fails as a selector failure.

**Retries and timeouts.** When the whole list fails to resolve, the runner re-walks the full candidate list in a loop until the step timeout expires — a single pass would race slow renders. No separate retry counter: the timeout is the retry budget. The workflow-level default step timeout is 30s (matching but explicitly set, not inherited from, the Python binding's default); per-step overrides exist per ds8zyn. Playwright's actionability checks (visible, stable, enabled, receives events) operate within each attempted action as usual.

**Drift visibility — both surfaces.** The Step Result already records which candidate matched (ds8zyn). It surfaces (a) per-step in the run detail (apx4rs renders it), and (b) as an aggregate Selector Drift warning badge on the step in the workflow editor, computed over recent runs — step-id stability across Versions (ds8zyn) exists to enable exactly this. The editor is where repair happens, so the warning lives there too. "Selector Drift" is now in docs/GLOSSARY.md.

**Partial runs.** A non-optional step failing for good stops the Run: executed steps keep their passed/failed Step Results, all remaining steps get Step Results with status `skipped`, and the Run terminates failed/step_failed (px25yw). A Batch continues to the next row when one row's Run fails — failed rows show among succeeded ones in the batch progress view (apx4rs); one bad row never strands the rest. (Distinct from cancelling a Batch, which skips remaining rows, per px25yw.)

**Repair path.** Primary: single-step element re-pick via the extension — the user opens the page, clicks the intended element, and a fresh record-time-verified candidate list replaces the step's old one. Escape hatch: hand-editing the selector list in the editor (selectors are plain stored data). Whole-workflow re-record always exists trivially. The re-pick flow is accepted extension scope: a "re-pick one element" mode distinct from full recording — this lands in the recording/editing spec (u8q8p3).

## Reason

Confirms f10wq3's recommendation with the user's sign-off: the peer-reviewed voting gain (29.5%) was measured over five XPath generators on 2015-era apps, not semantic locators, and voting can let converging broken locators out-vote correct ones. Ordered fallback over a record-time-verified ranked list is simpler and sufficient; visibility (drift surfacing) plus a cheap repair path (re-pick) covers maintenance without self-healing.
