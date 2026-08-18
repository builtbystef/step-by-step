---
id: g795ji
title: Publish, Versions, and the step diff
state: done
assignee: claude
priority: high
depends_on:
    - sl7h4j
parent: d8ux2s
created: 2026-08-14T06:02:01Z
updated: 2026-08-18T23:41:39Z
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

**claude** — 2026-08-18T23:41:39Z

Done. Publishing, the Versions it mints, restore, and the one comparison the publish modal and the Draft chip both read.

**What landed**

- `workflows/models.py` — `workflow_versions`, keyed by the pair `(workflow_id, number)` so the number is the Workflow's own count and the key itself refuses a number already minted. No `updated_at`, and nothing writes to the table after the insert. Migration `9d10b661a9f4`.
- `workflows/document.py` — the two derivations. `diff()` keys on Step ids and returns `{added, changed, removed}` of `{id, label}`; `draft_state()` compares the two stored documents whole and answers `never-published` / `unpublished-changes` / `in-sync`.
- `workflows/routes.py` — the five pinned routes with their `operation_id`s: `publishWorkflowVersion`, `listWorkflowVersions`, `getWorkflowVersion`, `restoreWorkflowVersion`, `getWorkflowDraftDiff`. All five reach the Workflow through the same org-scoped lookup, so another Organization's is 404 on every one of them.
- 16 HTTP seam tests in `apps/api/tests/integration/test_workflow_versions.py` against the real Postgres. It imports the Draft helpers from `test_workflows.py` rather than copying them — a Version is a Draft that stopped changing, and every test here starts by writing one.

**Decisions**

- **Publish copies the stored JSONB across as it is**, rather than re-serializing the Draft through the models. That is what makes the byte-match true a year later: a round trip through code that has changed since is exactly how a Version stops being what the editor was looking at.
- **Publish takes the Draft row's lock first** (`SELECT … FOR UPDATE`). Two publishes that read the same count would otherwise mint the same number, and the composite key would turn the loser's work into a database error instead of a second Version.
- **`POST /versions` answers `{number, created_at}`** — the pinned `{number}`, plus the time, so the publish and the list speak one `VersionSummary`.
- **`GET /draft/diff` also answers `state` and `latest_version`.** The issue asks the same derivation to yield the draft state, and one route answering both readers is what stops the modal and the chip from ever disagreeing. `latest_version` is null until a first publish.
- **A Step that only moved is in none of the three lists.** Positions shift whenever anything above them is inserted, so a diff that read them would report every later Step as changed and bury the one that was touched. The state still reads `unpublished-changes` for a reorder-only or Variables-only edit, because it compares whole documents — a test pins that pair of behaviours together, since it is the one place the two halves of the answer look inconsistent and are not.
- **A restored document is not revalidated.** It passed the rules at the save that preceded its publish, and a Version is executable forever; refusing to bring one back because a rule has since grown stricter would make it exactly not that.
- **The three diff lists carry no defaults**, so the generated client types them as always present and a reader renders "nothing changes" from an empty list rather than from a missing key.
- **The draft state is derived and never stored.** A stored flag would have to be set by each of the three paths that write a Draft — the editor's save, the recorder's finalize, a restore — and the one that forgot would leave a Workflow claiming to be in sync with a Version it no longer matches.

**For a reviewer**

- Immutability is asserted as the absence of a way in: the Version document URL answers reads and refuses PUT, PATCH, and DELETE with 405, and an edit to the Draft after a publish leaves the Version's document identical.
- Publishing an empty Draft is allowed. No criterion forbids it, and `5rkj33` refuses to *start* a Workflow that has no published Version, which is where that matters.
- `docs/ARCHITECTURE.md`'s Workflows section, `apps/api/openapi.json`, and the generated client are updated with this slice.
