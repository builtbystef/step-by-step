---
id: cn2w0f
title: Publish warns the Schedules it would strand
state: done
assignee: agent
priority: medium
depends_on:
    - fpzupm
    - fq0wr7
parent: nno9gj
created: 2026-08-14T19:52:25Z
updated: 2026-08-26T21:19:23Z
---

## What to build

The publish action warns **before it acts** when the new Version declares a non-secret Variable that an existing Schedule of that Workflow has no value for: the confirmation names those Schedules and states that they will stop firing until their values are set. This is one of the three channels (with the table and the banner) that stand in for notifications, which v1 does not have. The slice carries whatever read the confirmation needs — the candidate Version's declared Variables checked against each Schedule's value set — plus the dialog line itself.

## Acceptance criteria

- [ ] Publishing a Draft that adds a non-secret Variable `region` while two Schedules of the Workflow lack a value for it → the publish confirmation names both Schedules and states they will stop firing until their values are set; confirming publishes, and both Schedules then read `needs_values`.
- [ ] Publishing a Draft that strands no Schedule shows the normal confirmation with no warning.
- [ ] Cancelling at the warning leaves the Draft unpublished and every Schedule untouched.

## Notes

**agent** — 2026-08-26T21:19:23Z

Completed the publish-time warning for Schedules a new Version would strand.

Seams (from the spec's Testing Decisions, recorded because this was an unattended session): HTTP for the confirmation's read and the post-publish derived state; the existing `publishPlan` module for the dialog line. The spec rules editor UI automation out, so cancelling the modal is true by construction — the warning is a GET, and the only caller of `publishWorkflowVersion` is the confirm button.

What landed:
- `GET /api/workflows/{id}/draft/diff` gains `stranded_schedules`: enabled Schedules of this Workflow whose value set misses a non-secret Variable the candidate (Draft) declares. Each row is `{id, name, cron}`. State is still derived on read against the latest published Version, so the list is what the confirmation needs *before* anything is minted.
- Confirming still just publishes. Both Schedules then read `needs_values` with no write to their rows (fpzupm).
- A publish that strands no Schedule answers `[]`; the modal's warning is absent.
- Reading the diff mints nothing and leaves every Schedule untouched.
- `publishPlan` turns the list into the confirmation line: names both Schedules and states they will stop firing until their values are set. A blank name uses the recurrence sentence (`humanize`), the same rule the table uses. The words stay on the client.

Decisions:
- Extended the existing comparison rather than a second endpoint. The modal already fetches the diff only while open, and stranded Schedules are "what publishing would change".
- Paused Schedules are left out. They would not read `needs_values` after publish, and "will stop firing" would be a lie about a Schedule that is already not firing.
- Secret Variables do not strand anyone (they are not stored on a Schedule).

For a reviewer:
- What the module seam does not observe: that the warn Callout actually appears in the dialog. Check `publish-dialog.tsx` by eye.
- `pnpm check` / `pnpm test` equivalents were run via `vp check`, `.venv` ruff/ty, `vp test` (445), and the fast pytest tier; `uv run` cannot sync in this environment. Integration: the 19 tests in `test_workflow_versions.py` (including the three new ones) against the compose Postgres.
