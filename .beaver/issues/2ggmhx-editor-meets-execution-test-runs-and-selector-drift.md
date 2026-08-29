---
id: 2ggmhx
title: 'Editor meets execution: test runs and Selector Drift'
state: done
assignee: agent
priority: medium
depends_on:
    - y2fsy1
    - z8p5dp
    - 6ewr2p
    - m6s5me
parent: d8ux2s
created: 2026-08-14T06:04:19Z
updated: 2026-08-29T07:31:47Z
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

**agent** — 2026-08-29T07:31:44Z

Done. Test runs of the Draft and Selector Drift on the editor cards.

**Seams.** Spec puts editor UI automation out of scope, so: pure frontend modules read back with no DOM (`test-run.ts` — one field per Variable, secrets masked, never blocked by the publish-first sentence; `drift.ts` — rank above 0 is drift, the badge leads into the selector panel); the HTTP API against Postgres for the snapshot, the Version list, and the aggregate. 7 new Vitest tests; 4 new integration tests (freeze, drift, recent window, tenant isolation). The existing never-published test-run route still stands.

**What landed**

- Editor **Test run** action: a modal over the saved Draft, one field per declared Variable, secret ones `type=password`. `POST /api/workflows/{id}/runs` with `test: true`. Navigates to the new Run. Never-published is allowed. Unsaved editor changes are refused (the snapshot is the server Draft).
- `GET /api/workflows/{id}/selector-drift` — Step ids whose last ten Runs resolved through a candidate below rank 0. Amber **drifting** badge on the card; activating it expands the card and opens the existing selector panel (Re-pick and hand-edit already repair there).
- OpenAPI and the generated client regenerated.

**Decisions**

- **Recent is the last ten Runs**, the same window the catalog uses for median duration. Older drift does not badge.
- **Secret values stay in the vault.** The form asks for every Variable and masks the secret ones, matching the spec; the payload never carries them (ADR 0003 / the Run store). Execution still resolves Secrets at claim.
- **Unsaved refuses a test run**, same reason recording and Re-pick refuse: the snapshot is the server Draft, and starting against a dirty local copy would test something the person is not looking at.
- **The header Run is unchanged.** It still needs a published Version and still says the shared publish-first sentence. Test run is the editor's action.

**For a reviewer**

- `pnpm check` and `pnpm test` green. The four new integration tests pass against compose Postgres.
- Test-run field tests assert secrets never enter the body. Drift tests use rank 0 vs rank 2, the criterion's own distinction.
- No DOM test for the modal or the badge; look at `test-run-dialog.tsx` and the drift button on `step-card.tsx`.
