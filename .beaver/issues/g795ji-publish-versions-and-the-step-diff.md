---
id: g795ji
title: Publish, Versions, and the step diff
state: todo
priority: high
depends_on:
    - sl7h4j
parent: d8ux2s
created: 2026-08-14T06:02:01Z
updated: 2026-08-17T04:04:08Z
---

## What to build

The immutable half of the storage model. Publishing snapshots the Draft's whole document — steps and variables — into a numbered Version in a single insert; a Version is self-contained and executable forever. Versions can be listed and read but never written. A past Version can be restored to the Draft. A step-level diff, keyed on stable step ids, tells the user what a publish will change; the same derivation yields the three-state draft state the Workflows list and editor header render.

## Acceptance criteria

- [ ] Publish mints Version N+1 (starting at 1) whose document byte-matches the Draft at publish time; subsequent Draft edits leave every existing Version untouched, and no API route can modify a Version.
- [ ] Versions are listable (numbers, created times) and readable individually.
- [ ] The diff against the latest Version is computed by stable step id: with v1 published, editing step A's payload, adding step D, and removing step C from the Draft yields a diff of exactly changed [A], added [D], removed [C]; the publish flow exposes this diff before minting.
- [ ] Draft state derives as: no Versions → never-published; Draft differs from the latest Version → unpublished-changes; byte-equal → in-sync. Publishing flips unpublished-changes to in-sync; the next Draft edit flips it back.
- [ ] Restoring a past Version copies its document into the Draft with step ids preserved, leaving the Version itself untouched; the resulting draft state reflects the comparison against the latest Version.
- [ ] HTTP seam tests with a real Postgres cover the byte-match, immutability, the worked diff, the state transitions, and restore.

## Notes

**claude** — 2026-08-17T04:04:08Z

Pinned routes (this slice owns them): POST /api/workflows/{id}/versions → 201 {number} (publish, mints N+1); GET /api/workflows/{id}/versions → 200 [{number, created_at}]; GET /api/workflows/{id}/versions/{number} → 200 the document; POST /api/workflows/{id}/versions/{number}/restore → 200 (copies the document into the Draft); GET /api/workflows/{id}/draft/diff → 200 {added, changed, removed} by stable step id with labels, against the latest Version — the publish modal and the draft-state derivation both consume it. operation_id on each route.
