---
id: 2ggmhx
title: 'Editor meets execution: test runs and Selector Drift'
state: todo
priority: medium
depends_on:
    - y2fsy1
    - z8p5dp
    - 6ewr2p
    - m6s5me
parent: d8ux2s
created: 2026-08-14T06:04:19Z
updated: 2026-08-29T06:57:49Z
---

## What to build

The two editor features that need a running execution layer. A test run verifies edits safely: a modal collects per-run Variable values (secrets masked), the Run embeds its own frozen snapshot of the Draft document and is flagged a test run, and no Version is minted — Schedules and Batches keep executing the latest published Version. Selector Drift closes the repair loop: the editor is where repair happens, so the warning lives there, computed from recent Step Results' matched-candidate ranks.

## Acceptance criteria

- [ ] The test-run action opens a modal asking for a value per declared Variable, secret Variables masked; starting it creates a Run flagged as a test whose snapshot is the Draft document frozen at start — Draft edits made while it runs do not affect it — and the Version list is unchanged afterwards.
- [ ] A never-published Workflow can test-run its Draft; the shared publish-first sentence never blocks a test run.
- [ ] A Step whose recent Runs resolved through a lower-ranked candidate than the recorded best (matched rank above 0 in recent Step Results) shows an aggregate drift warning badge on its card; a Step resolving at rank 0 shows none.
- [ ] The drift badge leads into the existing selector panel, where Re-pick and hand editing already repair the target.

## Notes

**agent** — 2026-08-27T04:15:25Z

Blocked by m6s5me. The fourth acceptance criterion requires the drift badge to lead into the existing selector panel, but that panel does not exist yet: m6s5me is awaiting a user decision on the Re-pick confirmation contract. Complete m6s5me first; then this issue can connect the badge to its repair surface without inventing a second or temporary panel.

**agent** — 2026-08-29T06:57:49Z

Released back to todo so an implement-loop run can claim and complete it. The previous block (m6s5me — selector panel / Re-pick) is done; the four acceptance criteria still stand.
